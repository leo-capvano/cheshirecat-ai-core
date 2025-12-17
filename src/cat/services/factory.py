import asyncio
from typing import Type, TYPE_CHECKING

from cat import log
from cat.services.service import Service

if TYPE_CHECKING:
    from cat.looking_glass.execution_context import ExecutionContext


class ServiceRegistry:
    """
    Registry for service classes discovered from plugins.
    Stores service class definitions organized by type and slug.
    """

    def __init__(self):
        # { "service_type": { "slug": ServiceClass } }
        self._services: dict[str, dict[str, Type["Service"]]] = {}

    def register(self, service_class: Type["Service"]) -> None:
        """
        Register a service class.

        Parameters
        ----------
        service_class : Type[Service]
            The service class to register.
        """
        service_type = service_class.service_type
        slug = service_class.slug

        if not service_type:
            raise ValueError(f"Service {service_class.__name__} has no service_type")
        if not slug:
            raise ValueError(f"Service {service_class.__name__} has no slug")

        if service_type not in self._services:
            self._services[service_type] = {}

        self._services[service_type][slug] = service_class
        log.debug(f"Registered service: {service_type}:{slug} ({service_class.__name__})")

    def get(self, service_type: str, slug: str) -> Type["Service"] | None:
        """
        Get a service class by type and slug.

        Parameters
        ----------
        service_type : str
            The type of service (e.g., "agent", "memory").
        slug : str
            The slug identifier for the service.

        Returns
        -------
        Type[Service] | None
            The service class if found, None otherwise.
        """
        return self._services.get(service_type, {}).get(slug)

    def list_by_type(self, service_type: str) -> dict[str, Type["Service"]]:
        """
        List all services of a given type.

        Parameters
        ----------
        service_type : str
            The type of service to list.

        Returns
        -------
        dict[str, Type[Service]]
            Dictionary of slug -> ServiceClass for the given type.
        """
        return self._services.get(service_type, {})

    def list_all(self) -> dict[str, dict[str, Type["Service"]]]:
        """
        Get all registered services.

        Returns
        -------
        dict[str, dict[str, Type[Service]]]
            All services organized by type and slug.
        """
        return self._services


class ServiceContainer:
    """
    Container for singleton service instances.
    Provides thread-safe storage with lifecycle management.
    """

    def __init__(self):
        # {service_type: {slug: instance}}
        self._instances: dict[str, dict[str, "Service"]] = {}
        self._lock = asyncio.Lock()

    async def get(self, service_type: str, slug: str) -> Service | None:
        """
        Get a singleton instance if it exists.

        Parameters
        ----------
        service_type : str
            The type of service.
        slug : str
            The slug identifier.

        Returns
        -------
        Service | None
            The service instance if found, None otherwise.
        """
        async with self._lock:
            return self._instances.get(service_type, {}).get(slug)

    async def set(self, service_type: str, slug: str, instance: "Service") -> None:
        """
        Store a singleton instance.

        Parameters
        ----------
        service_type : str
            The type of service.
        slug : str
            The slug identifier.
        instance : Service
            The service instance to store.
        """
        async with self._lock:
            if service_type not in self._instances:
                self._instances[service_type] = {}
            self._instances[service_type][slug] = instance

    async def has(self, service_type: str, slug: str) -> bool:
        """
        Check if a singleton instance exists.

        Parameters
        ----------
        service_type : str
            The type of service.
        slug : str
            The slug identifier.

        Returns
        -------
        bool
            True if the instance exists, False otherwise.
        """
        async with self._lock:
            return slug in self._instances.get(service_type, {})

    async def clear(self) -> None:
        """
        Clear all singleton instances.
        Useful for testing or reset operations.
        """
        async with self._lock:
            self._instances.clear()


class ServiceFactory:
    """
    Factory for creating and managing service instances.
    Handles both singleton and request-scoped lifecycles.
    """

    def __init__(self):
        self.registry = ServiceRegistry()
        self.container = ServiceContainer()

    async def get_service(
        self,
        service_type: str,
        slug: str,
        ctx: "ExecutionContext",
        raise_error: bool = False
    ) -> Service | None:
        """
        Get a service instance based on its lifecycle.
        - Singleton services: retrieved from container (or created if first access)
        - Request services: new instance created each time

        Parameters
        ----------
        service_type : str
            The type of service (e.g., "agent", "memory").
        slug : str
            The slug identifier for the service.
        ctx : ExecutionContext
            The execution context (for singletons, should be gctx).
        raise_error : bool
            If True, raises exception when service not found.

        Returns
        -------
        Service | None
            The service instance, or None if not found and raise_error=False.

        Raises
        ------
        Exception
            If service not found and raise_error=True.
            If service setup fails.
        """
        # Get service class from registry
        ServiceClass = self.registry.get(service_type, slug)

        if ServiceClass is None:
            if raise_error:
                available = list(self.registry.list_by_type(service_type).keys())
                raise Exception(
                    f'Service "{service_type}" with slug "{slug}" not found. '
                    f"Available: {available}"
                )
            return None

        lifecycle = ServiceClass.lifecycle

        if lifecycle == "singleton":
            return await self._get_or_create_singleton(ServiceClass, ctx)
        elif lifecycle == "request":
            return await self._create_request_service(ServiceClass, ctx)
        else:
            raise Exception(f"Unknown lifecycle: {lifecycle}")

    async def _get_or_create_singleton(
        self,
        ServiceClass: Type[Service],
        ctx: "ExecutionContext"
    ) -> Service:
        """
        Get or create a singleton service instance.

        Parameters
        ----------
        ServiceClass : Type[Service]
            The service class to instantiate.
        ctx : ExecutionContext
            The execution context (must be gctx, no user).

        Returns
        -------
        Service
            The singleton instance.
        """
        service_type = ServiceClass.service_type
        slug = ServiceClass.slug

        # Check if already in container
        if await self.container.has(service_type, slug):
            return await self.container.get(service_type, slug)

        # Ensure we're using global context for singletons
        gctx = ctx if ctx.user is None else ctx.ccat.gctx
        if gctx.user is not None:
            raise Exception(
                f"SingletonService {service_type}:{slug} must be instantiated "
                "with global context (gctx), no user."
            )

        # Create new instance
        log.debug(f"Creating singleton: {service_type}:{slug}")
        instance = ServiceClass(gctx)

        try:
            await instance.setup()
        except Exception as e:
            raise Exception(
                f"Failed to setup singleton {service_type}:{slug}: {e}"
            ) from e

        # Store in container
        await self.container.set(service_type, slug, instance)

        return instance

    async def _create_request_service(
        self,
        ServiceClass: Type["Service"],
        ctx: "ExecutionContext"
    ) -> "Service":
        """
        Create a new request-scoped service instance.

        Parameters
        ----------
        ServiceClass : Type[Service]
            The service class to instantiate.
        ctx : ExecutionContext
            The execution context (with user).

        Returns
        -------
        Service
            A fresh service instance.
        """
        service_type = ServiceClass.service_type
        slug = ServiceClass.slug

        log.debug(f"Creating request service: {service_type}:{slug}")
        instance = ServiceClass(ctx)

        try:
            await instance.setup()
        except Exception as e:
            raise Exception(
                f"Failed to setup request service {service_type}:{slug}: {e}"
            ) from e

        return instance

    async def warmup_singletons(self, gctx: "ExecutionContext") -> None:
        """
        Pre-instantiate all singleton services at bootstrap.
        Fails fast if any singleton setup fails.

        Parameters
        ----------
        gctx : ExecutionContext
            The global execution context (no user).
        """
        log.info("Warming up singleton services...")

        for service_type, services in self.registry.list_all().items():
            for slug, ServiceClass in services.items():
                if ServiceClass.lifecycle == "singleton":
                    try:
                        await self._get_or_create_singleton(ServiceClass, gctx)
                        log.info(f"\t{service_type}:{slug}")
                    except Exception as e:
                        log.error(f"\t{service_type}:{slug} - {e}")
                        raise

    async def shutdown(self) -> None:
        """
        Shutdown all singleton services.
        Calls teardown() on each service if available.
        """
        log.info("Shutting down singleton services...")

        for service_type, services in self.container._instances.items():
            for slug, instance in services.items():
                if hasattr(instance, "teardown"):
                    try:
                        await instance.teardown()
                        log.info(f"{service_type}:{slug} teardown")
                    except Exception as e:
                        log.error(f"{service_type}:{slug} teardown failed: {e}")

        await self.container.clear()
        log.info("Shutdown complete.")

    async def reset(self) -> None:
        """
        Reset the factory by shutting down all services and clearing registries.
        Used when plugins are toggled or settings change.
        """
        log.info("Resetting factory...")

        # Shutdown existing singletons
        await self.shutdown()

        # Clear registry
        self.registry._services.clear()

        log.info("Factory reset complete.")
