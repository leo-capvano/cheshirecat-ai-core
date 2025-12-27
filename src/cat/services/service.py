from typing import Union, Literal, Type, Dict, Any, TYPE_CHECKING
from pydantic import BaseModel, ConfigDict

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

class ServiceMetadata(BaseModel):
    """Metadata about a service."""

    lifecycle: LifeCycle
    service_type: str
    slug: str
    name: str
    description: str
    plugin_id: str | None
    settings_schema: dict | None = None

    # allow extra fields
    model_config = ConfigDict(extra="allow")

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
        Override in subclasses to provide settings.

        Returns
        -------
        Type[BaseModel] | None
            Pydantic BaseModel class, or None if no settings.

        Example
        -------
        ```python
        from pydantic import BaseModel

        async def settings_model(self):
            class MyServiceSettings(BaseModel):
                api_key: str
                timeout: int = 30

            return MyServiceSettings
        ```
        """
        
        return None

    async def load_settings(self) -> Dict[str, Any]:
        """
        Load service settings.
        Override in subclasses to implement settings storage.

        Returns
        -------
        dict
            The service settings as a dictionary.
        """
        return {}

    async def save_settings(self, settings: BaseModel | Dict[str, Any]) -> Dict[str, Any]:
        """
        Save service settings.
        Override in subclasses to implement settings storage.

        Parameters
        ----------
        settings : BaseModel | dict
            The settings to save (as Pydantic model or dict).

        Returns
        -------
        dict
            The saved settings as dict.
        """
        # Convert BaseModel to dict if needed
        if isinstance(settings, BaseModel):
            return settings.model_dump()
        return settings

    async def get_meta(self) -> ServiceMetadata:
        """
        Get service metadata.

        Returns
        -------
        ServiceMetadata
            Service metadata including settings schema.
        """
        model = await self.settings_model()
        settings_schema = model.model_json_schema() if model else None

        return ServiceMetadata(
            service_type=self.service_type,
            lifecycle=self.lifecycle,
            slug=self.slug,
            name=self.name,
            description=self.description,
            plugin_id=self.plugin_id,
            settings_schema=settings_schema
        )


class SingletonService(Service):
    """
    Base class for singleton services (Auth, ModelProvider, Memory).

    Global services are instantiated once during CheshireCat bootstrap
    and reused across all requests.

    Settings are persisted in the database.
    """

    lifecycle = "singleton"

    async def load_settings(self) -> Dict[str, Any]:
        """
        Load service settings from plugin namespace.
        Settings are stored under {service_type}_{slug} key in plugin settings.

        Returns
        -------
        dict
            The service settings, or empty dict if none saved.
        """
        if not self.plugin:
            return {}

        plugin_dict = await self.plugin.load_settings()
        namespace = f"{self.service_type}_{self.slug}"
        return plugin_dict.get(namespace, {})

    async def save_settings(self, settings: BaseModel | Dict[str, Any]) -> Dict[str, Any]:
        """
        Save service settings to plugin namespace.
        Updates only this service's namespace within the plugin settings.

        Parameters
        ----------
        settings : BaseModel | dict
            The complete settings to save for this service.

        Returns
        -------
        dict
            The saved settings.
        """
        if not self.plugin:
            raise Exception("Cannot save settings for service without plugin")

        # Convert BaseModel to dict if needed
        if isinstance(settings, BaseModel):
            settings = settings.model_dump()

        # Load full plugin settings
        plugin_dict = await self.plugin.load_settings()

        # Update this service's namespace
        namespace = f"{self.service_type}_{self.slug}"
        plugin_dict[namespace] = settings

        # Save back to plugin
        await self.plugin.save_settings(plugin_dict)

        return settings


class RequestService(Service, LLMMixin, EventStreamMixin):
    """
    Base class for request-scoped services (e.g. Agent).
    Request services are instantiated fresh for each request and related to a specific user.

    Settings are persisted per-user in user settings.
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

    async def load_settings(self) -> Dict[str, Any]:
        """
        Load service settings from user namespace.
        Settings are stored under {service_type}_{slug} key in user settings.

        Returns
        -------
        dict
            The service settings for this user, or empty dict if none saved.
        """
        user_dict = await self.user.load_settings()
        namespace = f"{self.service_type}_{self.slug}"
        return user_dict.get(namespace, {})

    async def save_settings(self, settings: BaseModel | Dict[str, Any]) -> Dict[str, Any]:
        """
        Save service settings to user namespace.
        Updates only this service's namespace within the user settings.

        Parameters
        ----------
        settings : BaseModel | dict
            The complete settings to save for this service.

        Returns
        -------
        dict
            The saved settings.
        """
        # Convert BaseModel to dict if needed
        if isinstance(settings, BaseModel):
            settings = settings.model_dump()

        # Load full user settings
        user_dict = await self.user.load_settings()

        # Update this service's namespace
        namespace = f"{self.service_type}_{self.slug}"
        user_dict[namespace] = settings

        # Save back to user
        await self.user.save_settings(user_dict)

        return settings
