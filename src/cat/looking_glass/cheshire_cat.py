import sys
from typing import TYPE_CHECKING

from rich import inspect

from cat import log
from cat.protocols.model_context.client import MCPClients
from cat.mad_hatter.mad_hatter import MadHatter
from .execution_context import ExecutionContext

if TYPE_CHECKING:
    from cat.base import Auth, Agent, ModelProvider, Memory, Service


class CheshireCat:
    """
    The Cheshire Cat.

    Main class that manages the whole AI application.
    It contains references to all the main modules and is responsible for application bootstrapping.

    In most cases you will not need to interact with this class directly, but rather
    with `ctx` (`ExecutionContext`) which will be available in your plugin's agents, hooks, tools and endpoints.
    """

    async def bootstrap(self, fastapi_app):
        """Cheshire Cat initialization.

        At bootstraps it loads all main components and services added by plugins.
        """

        # ^._.^

        # execution context for global services, not user/request bound
        self.gctx = ExecutionContext(self)

        try:
            # reference to the FastAPI object
            self.fastapi_app = fastapi_app
            # reference to the cat in fastapi state
            fastapi_app.state.ccat = self

            # instantiate MadHatter
            self.mad_hatter = MadHatter()
            self.mad_hatter.on_refresh_callbacks.append(
                self.on_mad_hatter_refresh
            )
            # Preinstall plugins if needed
            await self.mad_hatter.preinstall_plugins()
            # Trigger plugin discovery
            await self.mad_hatter.find_plugins()
            
            # allows plugins to do something before cat components are loaded
            await self.mad_hatter.execute_hook(
                # TODOV2: cover legacy hooks
                "before_bootstrap", None, self.gctx
            )
            
            # init MCP clients cache
            self.mcp_clients = MCPClients()

            # allows plugins to do something after the cat bootstrap is complete
            await self.mad_hatter.execute_hook(
                "after_bootstrap", None, self.gctx
            )

        except Exception:
            log.error("Error during CheshireCat bootstrap. Exiting.")
            sys.exit()

    async def on_mad_hatter_refresh(self):
        """Refresh CheshireCat components when MadHatter is refreshed."""
        
        await self.warmup_services()

        # update endpoints
        self.refresh_endpoints()

        # TODOV2: cache plugin settings (maybe not here, in the plugin obj)

        # allow plugins to hook the refresh (e.g. to embed tools)
        await self.mad_hatter.execute_hook(
            "after_mad_hatter_refresh", None, self.gctx
        )

        log.welcome()

    async def warmup_services(self):
        """Warmup long lived services."""

        # avoid circular imports
        from cat.services.auth.default import DefaultAuth
        from cat.services.agents.default import DefaultAgent
        from cat.services.model_provider.default import DefaultModelProvider
        from cat.services.service import SingletonService

        self.services = self.mad_hatter.service_classes

        # always have a default agent
        if not "agent" in self.services:
            self.services["agent"] = {}
        self.services["agent"]["default"] = DefaultAgent

        # if no auth or models provided by plugins, add defaults
        if "auth" not in self.services:
            self.services["auth"] = { "default": DefaultAuth }
        if "model_provider" not in self.services:
            self.services["model_provider"] = { "default": DefaultModelProvider }

        # actual warmup - instantiate SingletonService singletons
        self.service_instances = {}
        for type, services in self.services.items():
            self.service_instances[type] = {}
            for slug, ServiceClass in services.items():
                if issubclass(ServiceClass, SingletonService):
                    self.service_instances[type][slug] = \
                        await ServiceClass.get_instance(self.gctx)        

    def refresh_endpoints(self):
        """Sync plugin endpoints in the fastapi app."""

        # remove all plugin Endpoint routes from fastapi app
        routes_to_remove = []
        for route in self.fastapi_app.routes:
            if hasattr(route.endpoint, 'plugin_id'):
                routes_to_remove.append(route)
        for route in routes_to_remove:
            self.fastapi_app.routes.remove(route)
        
        # add the new list
        for e in self.mad_hatter.endpoints:
            self.fastapi_app.include_router(e)
        
        # reset openapi schema
        self.fastapi_app.openapi_schema = None

    @property
    def auth_handlers(self) -> dict[str, "Auth"]:
        """Get all auth handlers instances as a dictionary slug -> instance."""
        
        return self.service_instances.get("auth", {})



