from typing import Union, Literal, Type, Dict, Any, TYPE_CHECKING
from inspect import isclass
from pydantic import BaseModel

from cat.mixin.llm import LLMMixin
from cat.mixin.stream import EventStreamMixin

if TYPE_CHECKING:
    from fastapi import Request
    from cat.looking_glass.cheshire_cat import CheshireCat
    from cat.looking_glass.hook_context import HookContext
    from cat.auth.user import User
    from cat.mad_hatter.mad_hatter import MadHatter
    from cat.mad_hatter.plugin import Plugin
    from cat.services.__factory import ServiceFactory
    from cat.protocols.model_context.client import MCPClients

LifeCycle = Literal["singleton", "request"]

class Service:
    """
    Base class for plugin defined services.
    Do not subclass this directly - use SingletonService or RequestService instead.
    """

    service_type: str = "base"
    lifecycle: LifeCycle | None = None
    slug: str | None = None
    name: str | None = None
    description: str | None = None
    plugin_id: str | None = None

    ccat: "CheshireCat"

    @property
    def factory(self) -> "ServiceFactory":
        """Access to the ServiceFactory."""
        return self.ccat.factory

    @property
    def mad_hatter(self) -> "MadHatter":
        """Access to the MadHatter plugin manager."""
        return self.ccat.mad_hatter
    
    @property
    def plugin(self) -> Union["Plugin", None]:
        """Access to the Plugin that provided this service, if any."""
        if self.plugin_id is None:
            return None
        return self.mad_hatter.plugins[self.plugin_id]

    @property
    def mcp_clients(self) -> "MCPClients":
        """Access to MCP clients."""
        return self.ccat.mcp_clients

    async def setup(self) -> None:
        """
        Async setup for the service (e.g. load API keys from settings).
        Override in subclasses.
        """
        pass

    async def teardown(self) -> None:
        """
        Async cleanup for the service (e.g. close connections, cleanup resources).
        Called during shutdown for singleton services.
        Override in subclasses if cleanup is needed.
        """
        pass

    async def execute_hook(self, hook_name: str, default_value: Any) -> Any:
        """
        Execute a hook for plugins to be intercepted.
        MadHatter will build HookContext internally from this service.

        Parameters
        ----------
        hook_name : str
            Name of the hook to execute.
        default_value : Any
            Default value if hook doesn't modify it.

        Returns
        -------
        Any
            The value after hook execution.
        """
        return await self.mad_hatter.execute_hook(
            hook_name,
            default_value,
            caller=self
        )

    async def settings_model(self) -> Type[BaseModel] | None:
        """
        Return the Pydantic model for service settings.
        Override in subclasses to provide dynamic settings schemas.

        By default, returns the nested `Settings` class if one is declared
        on the service class. Override this method to provide dynamic schemas
        (e.g., schemas that depend on installed plugins). When both a nested
        `Settings` class and a `settings_model()` override exist, the override
        takes precedence.

        Returns
        -------
        Type[BaseModel] | None
            Pydantic BaseModel class, or None if no settings.

        Example
        -------
        ```python
        from pydantic import BaseModel

        class MyService(SingletonService):
            # Preferred: nested Settings class
            class Settings(BaseModel):
                api_key: str
                timeout: int = 30

            # OR: override settings_model() for dynamic schemas
            async def settings_model(self):
                class DynamicSettings(BaseModel):
                    api_key: str
                return DynamicSettings
        ```
        """
        # Default: return nested Settings class if declared
        nested = getattr(self.__class__, 'Settings', None)
        if nested is not None and isinstance(nested, type) and issubclass(nested, BaseModel):
            return nested
        return None

    def _settings_db_key(self) -> str:
        """DB key for this service's settings: settings_{plugin_id}_{service_type}_{slug}."""
        return f"settings_{self.plugin_id}_{self.service_type}_{self.slug}"

    async def load_settings(self) -> Dict[str, Any]:
        """
        Load service settings from KeyValueDB (installation-wide).
        Also populates `self.settings` as a typed Pydantic model instance.

        Returns
        -------
        dict
            The service settings, or empty dict if none saved.
        """
        from cat.db import DB

        raw = await DB.load(self._settings_db_key(), default={})
        self._populate_settings(raw)
        return raw

    async def save_settings(self, settings: BaseModel | Dict[str, Any]) -> Dict[str, Any]:
        """
        Save service settings to KeyValueDB (installation-wide).
        Also updates `self.settings` as a typed Pydantic model instance.

        Parameters
        ----------
        settings : BaseModel | dict
            The complete settings to save for this service.

        Returns
        -------
        dict
            The saved settings.
        """
        from cat.db import DB

        # Convert BaseModel to dict if needed
        if isinstance(settings, BaseModel):
            settings = settings.model_dump()

        await DB.save(self._settings_db_key(), settings)
        self._populate_settings(settings)
        return settings

    def _populate_settings(self, raw: Dict[str, Any]) -> None:
        """
        Populate `self.settings` as a typed Pydantic model from raw dict.
        If a Settings class exists and raw data is available, validates and
        creates a model instance. Otherwise sets `self.settings` to None or raw dict.
        """
        nested = getattr(self.__class__, 'Settings', None)
        if nested is not None and isclass(nested) and issubclass(nested, BaseModel):
            if raw:
                try:
                    self.settings = nested.model_validate(raw)
                except Exception:
                    # fallback to defaults if saved data is invalid
                    self.settings = nested()
            else:
                self.settings = nested()
        elif raw:
            # No Settings class but there's data (e.g. settings_model() override)
            self.settings = raw
        else:
            self.settings = None



class SingletonService(Service):
    """
    Base class for singleton services (Auth, ModelProvider, Memory).

    Global services are instantiated once during CheshireCat bootstrap
    and reused across all requests.

    Settings are persisted installation-wide in KeyValueDB.
    """

    lifecycle = "singleton"


class RequestService(Service, LLMMixin, EventStreamMixin):
    """
    Base class for request-scoped services (e.g. Agent).
    Request services are instantiated fresh for each request and related to a specific user.

    Settings are persisted installation-wide in KeyValueDB (admin-configured defaults).
    """

    lifecycle = "request"
    request: "Request"

    @property
    def user(self) -> "User":
        """Access the current user from request state."""
        return self.request.state.user

    @property
    def user_id(self) -> str:
        """Get the current user ID."""
        return self.user.id
