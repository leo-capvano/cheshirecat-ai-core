import sys

from cat.factory import Factory
from cat.protocols.model_context.client import MCPClients
from cat.mad_hatter.decorators.endpoint import CatEndpoint
from cat.log import log
from cat.mad_hatter.mad_hatter import MadHatter


class CheshireCat:
    """The Cheshire Cat.

    This is the main class that manages the whole AI application.
    It contains references to all the main modules and is responsible
    for the bootstrapping of the application.

    In most cases you will not need to interact with this class directly, but rather
    with class `StrayCat`which will be available in your plugin's hooks, tools and endpoints.

    Attributes
    ----------
    todo : list
        Help needed TODO
    """

    async def bootstrap(self, fastapi_app):
        """Cat initialization.

        At init time the Cat executes the bootstrap,
        loading all main components and components added by plugins.
        """

        # bootstrap the Cat! ^._.^

        try:
            # reference to the FastAPI object
            self.fastapi_app = fastapi_app
            # reference to the cat in fastapi state
            fastapi_app.state.ccat = self
            self.core_routes_sign = []
            for r in fastapi_app.routes:
                signature = self.get_route_signature(r)
                self.core_routes_sign.append(signature)

            # init Factory
            self.factory = Factory()

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
            await self.mad_hatter.execute_hook("before_cat_bootstrap", cat=self)
            
            # init MCP clients cache
            self.mcp_clients = MCPClients()

            # allows plugins to do something after the cat bootstrap is complete
            await self.mad_hatter.execute_hook("after_cat_bootstrap", cat=self)
        except Exception:
            log.error("Error during CheshireCat bootstrap. Exiting.")
            sys.exit()

        print("\n^._.^\n")

    async def on_mad_hatter_refresh(self):

        # Get factory objects from plugins
        await self.factory.load_objects(self)

        self.auth_handlers = self.factory.get_objects("auth_handler")
        self.llms = self.factory.get_objects("llm")
        self.agents = self.factory.get_objects("agent")
        self.mcps = self.factory.get_objects("mcp")

        # update endpoints
        self.refresh_endpoints()

        # allow plugins to hook the refresh (e.g. to embed tools)
        await self.mad_hatter.execute_hook("after_mad_hatter_refresh", cat=self)

    def refresh_endpoints(self):
        """Sync plugin endpoints with the fastapi app."""

        log.info(self.core_routes_sign)

        # create a signature for every custom endpoint route
        custom_routes_sign = []
        for e in self.mad_hatter.endpoints:
            for r in e.routes:
                signature = self.get_route_signature(r)
                custom_routes_sign.append(signature)
                log.info(signature)

        # remove all CatEndpoint routes from fastapi app
        routes_to_remove = []
        for route in self.fastapi_app.routes:
            signature = self.get_route_signature(route)
            if signature not in self.core_routes_sign:
                log.critical(route.plugin_id)
                routes_to_remove.append(route)

        for route in routes_to_remove:
            log.error(signature)
            self.fastapi_app.routes.remove(route)
            if route in self.fastapi_app.router.routes:
                self.fastapi_app.router.routes.remove(route)
            self.fastapi_app.openapi_schema = None  # reset openapi schema
        
        # add the new list
        for e in self.mad_hatter.endpoints:
            self.fastapi_app.include_router(e)
            self.fastapi_app.openapi_schema = None  # reset openapi schema


    def get_route_signature(self, route):
        try:
            signature = f"{route.name}-{route.path}-{route.tags}-{route.methods}"
        except:
            signature = f"{route.name}-{route.path}"
        return signature

    @property
    def plugin(self):
        """Access plugin object (used from within a plugin)."""

        return self.mad_hatter.get_plugin()


