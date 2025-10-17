import sys
from uuid import uuid4

from cat.db.models import SettingDB
from cat.factory.factory import Factory
from cat.protocols.model_context.client import MCPClients
from cat.log import log
from cat.mad_hatter.mad_hatter import MadHatter


class CheshireCat:
    """The Cheshire Cat.

    This is the main class that manages the whole AI application.
    It contains references to all the main modules and is responsible for the bootstrapping of the application.

    In most cases you will not need to interact with this class directly, but rather with class `StrayCat` which will be available in your plugin's hooks, tools and endpoints.

    Attributes
    ----------
    todo : list
        Help needed TODO
    """

    # will be called at first instantiation in fastapi lifespan
    async def bootstrap(self, fastapi_app):
        """Cat initialization.

        At init time the Cat executes the bootstrap, loading all main components and components added by plugins.
        """

        # bootstrap the Cat! ^._.^

        try:
            # reference to the FastAPI object
            self.fastapi_app = fastapi_app
            # reference to the cat in fastapi state
            fastapi_app.state.ccat = self

            # ensure core DB settings
            await self.populate_db()

            # instantiate MadHatter
            self.mad_hatter = MadHatter()
            self.mad_hatter.on_refresh_callbacks.append(
                self.on_mad_hatter_refresh
            )
            
            # init Factory
            self.factory = Factory()

            #  Trigger plugin discovery
            await self.mad_hatter.find_plugins()
            
            # allows plugins to do something before cat components are loaded
            self.mad_hatter.execute_hook("before_cat_bootstrap", cat=self)
            
            # init MCP clients cache
            self.mcp_clients = MCPClients()

            # allows plugins to do something after the cat bootstrap is complete
            self.mad_hatter.execute_hook("after_cat_bootstrap", cat=self)
        except Exception:
            log.error("Error during CheshireCat bootstrap. Exiting.")
            sys.exit()

        print("Ready ^._.^")

    async def populate_db(self):
        """Force minimal settings into core DB."""

        initial_settings = {
            "active_plugins": [],
            "installation_id": [str(uuid4())],
        }

        for name, value in initial_settings.items():
            setting = await SettingDB.get_or_none(name=name)
            if setting is None:
                setting = SettingDB(name=name, value=value)
                await setting.save()

                # only at first startup
                if name == "installation_id":
                    log.welcome()

    async def on_mad_hatter_refresh(self):
        
        # Get objects from plugins
        await self.factory.load_objects(self.mad_hatter)

        self.auth_handlers = self.factory.get_objects("auth_handler")
        self.llms = self.factory.get_objects("llm")
        self.embedders = self.factory.get_objects("embedder")
        self.agents = self.factory.get_objects("agent")
        self.mcps = self.factory.get_objects("mcp")

        # update endpoints
        for endpoint in self.mad_hatter.endpoints:
            endpoint.activate(self.fastapi_app)

        # allow plugins to hook the refresh (e.g. to embed tools)
        self.mad_hatter.execute_hook("after_mad_hatter_refresh", cat=self)

    


