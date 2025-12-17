from typing import Literal, ClassVar, TYPE_CHECKING
from pydantic import BaseModel, ConfigDict

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

    async def get_meta(self) -> ServiceMetadata:
        """Get service metadata."""
        return ServiceMetadata(
            service_type=self.service_type,
            lifecycle=self.lifecycle,
            slug=self.slug,
            name=self.name,
            description=self.description,
            plugin_id=self.plugin_id
        )


class SingletonService(Service):
    """
    Base class for singleton services (Auth, ModelProvider, Memory).

    Global services are instantiated once during CheshireCat bootstrap
    and reused across all requests.

    Example:
        class MyAuth(SingletonService):
            service_type = "auth"
            slug = "my_auth"

            async def setup(self):
                # Load API keys, etc.
                self.api_key = await self.load_api_key()
    """

    lifecycle = "singleton"
    _instance: ClassVar["SingletonService"] = None

    @classmethod
    async def get_instance(cls, ctx: "ExecutionContext") -> "SingletonService":
        """
        Get or create the singleton instance.

        Parameters
        ----------
        ctx : ExecutionContext
            Execution context (for singleton services, ctx has no user).

        Returns
        -------
        SingletonService
            The singleton instance.
        """
        if cls._instance is None:
            # Use the global context from CheshireCat
            gctx = ctx if ctx.user is None else ctx.ccat.gctx
            if gctx.user is not None:
                raise Exception("SingletonService must be instantiated with global context (gctx), no user.")
            cls._instance = cls(gctx)
            await cls._instance.setup()
        return cls._instance


class RequestService(Service):
    """
    Base class for request-scoped services (e.g. Agent).
    Request services are instantiated fresh for each request and related to a specific user.
    """

    lifecycle = "request"

    @classmethod
    async def get_instance(cls, ctx: "ExecutionContext") -> "RequestService":
        """
        Get a new instance of the service.

        Parameters
        ----------
        ctx : ExecutionContext
            Execution context.

        Returns
        -------
        RequestService
            A new service instance.
        """
        instance = cls(ctx)
        await instance.setup()
        return instance