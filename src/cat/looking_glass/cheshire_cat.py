import sys
from typing import TYPE_CHECKING

from rich import inspect

from cat import log
from cat.protocols.model_context.client import MCPClients
from cat.mad_hatter.mad_hatter import MadHatter
from cat.services.factory import ServiceFactory

if TYPE_CHECKING:
    from cat.base import Auth
    from cat.mad_hatter.plugin import Plugin


class CheshireCat:
    """
    The Cheshire Cat.

    Main class that manages the whole AI application.
    It contains references to all the main modules and is responsible for application bootstrapping.
    """

    async def bootstrap(self, fastapi_app):
        """Cheshire Cat initialization.

        At bootstraps it loads all main components and services added by plugins.
        """

        # ^._.^

        # service factory for managing service lifecycle
        self.factory = ServiceFactory(self)

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
                "before_cat_bootstrap", None, caller=self
            )

            # init MCP clients cache
            self.mcp_clients = MCPClients()

            # allows plugins to do something after the cat bootstrap is complete
            await self.mad_hatter.execute_hook(
                "after_cat_bootstrap", None, caller=self
            )

        except Exception:
            log.error("Error during CheshireCat bootstrap. Exiting.")
            sys.exit()

    async def on_mad_hatter_refresh(self):
        """Refresh CheshireCat components when MadHatter is refreshed."""

        
        # reindex and warmup services
        await self.refresh_factory()

        # update endpoints
        self.refresh_endpoints()

        # TODOV2: cache plugin settings (maybe not here, in the plugin obj)

        # allow plugins to hook the refresh
        await self.mad_hatter.execute_hook(
            "after_mad_hatter_refresh", None, caller=self
        )

        log.welcome()

    async def refresh_factory(self):
        """Warmup long lived services."""

        # avoid circular imports
        from cat.services.auths.default import DefaultAuth
        from cat.services.agents.default import DefaultAgent
        from cat.services.model_providers.default import DefaultModelProvider
        
        # Reset factory (shutdown existing services and clear registry)
        await self.factory.teardown()

        # Register all services from plugins
        for service_type, services in self.mad_hatter.service_classes.items():
            for slug, ServiceClass in services.items():
                self.factory.register(ServiceClass)

        # Register default agent
        self.factory.register(DefaultAgent)

        # If no auth or model_provider from plugins, use defaults
        if not "auths" in self.factory.class_index:
            self.factory.register(DefaultAuth)
        if not "model_providers" in self.factory.class_index:
            self.factory.register(DefaultModelProvider)

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

    async def get_llm(self, slug: str, request=None):
        """
        Get an LLM instance by its slug.

        Parameters
        ----------
        slug : str
            The LLM slug in format "provider:model" (e.g., "openai:gpt-4").
        request : Request, optional
            The FastAPI request (for future extensibility).

        Returns
        -------
        BaseChatModel
            The LLM instance.
        """

        if ":" in slug:
            provider_slug, model_slug = slug.split(":", 1)
        else:
            provider_slug, model_slug = "default", slug

        provider = await self.factory.get(
            "model_providers",
            provider_slug,
            raise_error=True
        )

        return await provider.get_llm(model_slug)

    async def get_embedder(self, slug: str, request=None):
        """
        Get an Embedder instance by its slug.

        Parameters
        ----------
        slug : str
            The embedder slug in format "provider:model" (e.g., "openai:text-embedding-3-small").
        request : Request, optional
            The FastAPI request (for future extensibility).

        Returns
        -------
        Embeddings
            The embedder instance.
        """
        if ":" in slug:
            provider_slug, model_slug = slug.split(":", 1)
        else:
            provider_slug, model_slug = "default", slug

        provider = await self.factory.get(
            "model_providers",
            provider_slug,
            raise_error=True
        )

        return await provider.get_embedder(model_slug)

    async def get_auth_handlers(self) -> dict[str, "Auth"]:
        """
        Get all auth handlers instances as a dictionary slug -> instance.

        Returns
        -------
        dict[str, Auth]
            Dictionary of auth handler instances.
        """
        ahs = {}
        for slug in self.factory.class_index.get("auths", {}):
            ahs[slug] = await self.factory.get("auths", slug)
        return ahs
    
    @property
    def plugin(self) -> "Plugin":
        """Access to the Plugin that provided this service, if any."""
        return self.mad_hatter.get_plugin()

