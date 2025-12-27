from typing import List, Dict, Type, Union, TYPE_CHECKING
from fastapi import Request
from punq import Container, Scope

from cat import log

if TYPE_CHECKING:
    from cat.looking_glass.cheshire_cat import CheshireCat
    from cat.services.service import Service


class ServiceFactory:

    def __init__(self, ccat: "CheshireCat"):
        self.ccat = ccat
        self.container = Container()
        self.class_index: Dict[str, Dict[str, Type["Service"]]] = {}

    def register(self, ServiceClass: Type["Service"]):
        if ServiceClass.lifecycle == "singleton":
            self.container.register(
                ServiceClass,
                scope=Scope.singleton,
            )
        else:
            self.container.register(ServiceClass)

        type, slug = ServiceClass.service_type, ServiceClass.slug
        if type not in self.class_index:
            self.class_index[type] = {}
        self.class_index[type][slug] = ServiceClass

    async def teardown(self):
        # stop singletons
        for instance in self.container._singletons.values():
            try:
                await instance.teardown()
            except Exception as e:
                log.error(f"Error during teardown of {instance}: {e}")
        # new container
        self.container = Container()
        self.class_index = {}
        
    async def get(
        self,
        type: str,
        slug: str,
        request: Request | None = None,
        raise_error: bool = True
    ) -> Union["Service", None]:
        """
        Get a service instance by type and slug.

        Parameters
        ----------
        type : str
            The type of service (e.g. "agent", "auth").
        slug : str
            The slug identifier for the service (e.g. "my_agent", "graph_memory").
        request : Request, optional
            The FastAPI request object, required for request-scoped services.
        raise_error : bool, optional
            Whether to raise an error if the service is not found. Default is True.

        Returns
        -------
        Service | None
            The service instance if found, None otherwise.
        """
        
        try:
            ServiceClass = self.class_index[type][slug]
        except Exception:
            if raise_error:
                mex = f"Service of type '{type}' and slug '{slug}' not found"
                log.error(mex)
                raise Exception(mex)
            return None

        # Punq resolves (eventual) constructor dependencies automatically, if they are registered
        service = self.container.resolve(ServiceClass)

        # Inject CheshireCat ref and request ref for request-scoped services
        service.ccat = self.ccat # nasty reference to the app. I don't care
        if service.lifecycle == "request":
            if request is None:
                raise Exception(
                    f"Request object must be provided for request-scoped service {ServiceClass.__name__}")
            service.request = request

        # Post-construction injection: resolve 'requires' dict
        requires = getattr(ServiceClass, 'requires', {})
        for service_type, slugs in requires.items():
            print("\t", service_type, slugs)
            if isinstance(slugs, str):
                resolved = await self.get(service_type, slugs, request=request, raise_error=False)
            else:
                resolved = []
                for s in slugs:
                    instance = await self.get(service_type, s, request=request, raise_error=False)
                    if instance:
                        resolved.append(instance)
            setattr(service, service_type, resolved)

        if not hasattr(service, '_setup_done'):
            await service.setup()
            service._setup_done = True
        return service
