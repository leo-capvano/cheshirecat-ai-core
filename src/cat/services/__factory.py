import asyncio
from typing import Type, TYPE_CHECKING

from cat import log
from cat.services.service import Service

if TYPE_CHECKING:
    from cat.looking_glass.cheshire_cat import CheshireCat
    from fastapi import Request


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
            The type of service (e.g., , "memory").
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

    def __init__(self, ccat: "CheshireCat"):
        """
        Initialize the service factory.

        Parameters
        ----------
        ccat : CheshireCat
            The CheshireCat instance that owns this factory.
        """
        self.ccat = ccat
        self.registry = ServiceRegistry()
        self.container = ServiceContainer()

    async def get_service(
        self,
        service_type: str,
        slug: str,
        request: "Request" = None,
        raise_error: bool = False
    ) -> Service | None:
        """
        Get a service instance based on its lifecycle.
        - Singleton services: retrieved from container (or created if first access)
        - Request services: new instance created each time

        Parameters
        ----------
        service_type : str
            The type of service (e.g., , "memory").
        slug : str
            The slug identifier for the service.
        request : Request, optional
            The FastAPI Request object (required for request-scoped services).
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
            return await self._get_or_create_singleton(ServiceClass)
        elif lifecycle == "request":
            if request is None:
                raise Exception(
                    f"Request-scoped service {service_type}:{slug} requires a request parameter"
                )
            return await self._create_request_service(ServiceClass, request)
        else:
            raise Exception(f"Unknown lifecycle: {lifecycle}")

    async def _get_or_create_singleton(
        self,
        ServiceClass: Type[Service]
    ) -> Service:
        """
        Get or create a singleton service instance.

        Parameters
        ----------
        ServiceClass : Type[Service]
            The service class to instantiate.

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

        # Create new instance
        log.debug(f"Creating singleton: {service_type}:{slug}")
        instance = ServiceClass(self.ccat)

        try:
            await instance.setup()
        except Exception as e:
            log.error(f"Failed to setup singleton {service_type}_{slug}: {e}")
            return None

        # Store in container
        await self.container.set(service_type, slug, instance)

        return instance

    async def _create_request_service(
        self,
        ServiceClass: Type["Service"],
        request: "Request"
    ) -> "Service":
        """
        Create a new request-scoped service instance.

        Parameters
        ----------
        ServiceClass : Type[Service]
            The service class to instantiate.
        request : Request
            The FastAPI Request object.

        Returns
        -------
        Service
            A fresh service instance.
        """
        service_type = ServiceClass.service_type
        slug = ServiceClass.slug

        log.debug(f"Creating request service: {service_type}:{slug}")
        instance = ServiceClass(self.ccat, request)

        try:
            await instance.setup()
        except Exception as e:
            log.error(f"Failed to setup request service {service_type}_{slug}: {e}")
            return None

        return instance

    async def warmup_singletons(self) -> None:
        """
        Pre-instantiate all singleton services at bootstrap.
        Fails fast if any singleton setup fails.
        """
        log.info("Warming up singleton services...")

        for service_type, services in self.registry.list_all().items():
            for slug, ServiceClass in services.items():
                if ServiceClass.lifecycle == "singleton":
                    try:
                        await self._get_or_create_singleton(ServiceClass)
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
