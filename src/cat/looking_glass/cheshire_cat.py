import sys

from cat import log
from cat.factory import Factory
from cat.protocols.model_context.client import MCPClients
from cat.mad_hatter.mad_hatter import MadHatter


class CheshireCat:
    """The Cheshire Cat.

    This is the main class that manages the whole AI application.
    It contains references to all the main modules and is responsible
    for the bootstrapping of the application.

    In most cases you will not need to interact with this class directly, but rather
    with class `StrayCat` which will be available in your plugin's hooks, tools and endpoints.

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
            await self.mad_hatter.execute_hook("before_cat_bootstrap", None, self)
            
            # init MCP clients cache
            self.mcp_clients = MCPClients()

            # allows plugins to do something after the cat bootstrap is complete
            await self.mad_hatter.execute_hook("after_cat_bootstrap", None, self)

        except Exception:
            log.error("Error during CheshireCat bootstrap. Exiting.")
            sys.exit()

        log.welcome()

    async def on_mad_hatter_refresh(self):

        # Get factory objects from plugins
        await self.factory.load_objects(self)

        self.auth_handlers = self.factory.get_objects("auth_handler")
        self.llms = self.factory.get_objects("llm")
        self.embedders = self.factory.get_objects("embedder")
        #self.memories = self.factory.get_objects("memory")
        self.agents = self.factory.get_objects("agent")
        self.mcps = self.factory.get_objects("mcp")

        # update endpoints
        self.refresh_endpoints()

        # TODOV2: cache plugin settings (maybe not here, in the plugin obj)

        # allow plugins to hook the refresh (e.g. to embed tools)
        await self.mad_hatter.execute_hook("after_mad_hatter_refresh", None, self)

    def refresh_endpoints(self):
        """Sync plugin endpoints in the fastapi app."""

        # remove all CatEndpoint routes from fastapi app
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
    def plugin(self):
        """Access plugin object (used from within a plugin)."""

        return self.mad_hatter.get_plugin()


