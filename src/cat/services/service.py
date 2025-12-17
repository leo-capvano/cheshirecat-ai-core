from typing import Literal, Type, Dict, TYPE_CHECKING
from pydantic import BaseModel, ConfigDict, ValidationError

from cat.db import DB
from cat import log

if TYPE_CHECKING:
    from cat.looking_glass.execution_context import ExecutionContext

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

    def __init__(self, ctx: "ExecutionContext", *args, **kwargs):
        self.ctx = ctx

    async def setup(self):
        """
        Async setup for the service (e.g. load API keys from settings).
        Instance has already at disposal the ExecutionContext as `self.ctx`.
        Override in subclasses.
        """
        pass

    async def teardown(self):
        """
        Async cleanup for the service (e.g. close connections, cleanup resources).
        Called during shutdown for singleton services.
        Override in subclasses if cleanup is needed.
        """
        pass

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

    async def load_settings(self) -> Dict:
        """
        Load service settings.
        Override in subclasses to implement settings storage.

        Returns
        -------
        dict
            The service settings as a dictionary.
        """
        return {}

    async def save_settings(self, settings: BaseModel | Dict) -> Dict:
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
        """Get service metadata."""
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

    async def load_settings(self) -> Dict:
        """
        Load service settings from database.
        If settings exist but can't be validated against current model,
        returns empty dict (prevents blocking on schema changes).

        Returns
        -------
        dict
            The service settings, or empty dict if none saved or invalid.
        """
        db_key = f"service_{self.service_type}_{self.slug}_settings"

        loaded_settings = await DB.load(db_key)
        if loaded_settings is None:
            return {}

        # Validate against current model
        model = await self.settings_model()
        if model is not None:
            try:
                model.model_validate(loaded_settings)
            except ValidationError as e:
                log.warning(
                    f"Settings for {self.service_type}:{self.slug} are invalid "
                    f"(schema changed?). Resetting to defaults. Error: {e}"
                )
                return {}

        return loaded_settings

    async def save_settings(self, settings: BaseModel | Dict) -> Dict:
        """
        Save service settings to database.
        Full replacement, not partial merge.

        Parameters
        ----------
        settings : BaseModel | dict
            The complete settings to save (replaces existing).

        Returns
        -------
        dict
            The saved settings.
        """
        # Convert BaseModel to dict if needed
        if isinstance(settings, BaseModel):
            settings = settings.model_dump()

        db_key = f"service_{self.service_type}_{self.slug}_settings"

        return await DB.save(db_key, settings)


class RequestService(Service):
    """
    Base class for request-scoped services (e.g. Agent).
    Request services are instantiated fresh for each request and related to a specific user.

    Settings are transient and passed per-request, not persisted.
    """

    lifecycle = "request"

    async def save_settings(self, settings: Dict) -> Dict:
        """
        Request-scoped services do not support persistent settings.
        Settings should be provided per-request in the execution context.

        Raises
        ------
        Exception
            Always raises since request services cannot have persistent settings.
        """
        raise Exception(
            f"Request-scoped service {self.service_type}:{self.slug} "
            "does not support persistent settings. Settings are provided per-request."
        )