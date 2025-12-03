from typing import Callable
from copy import deepcopy

from cat import log
from cat.looking_glass.cheshire_cat import CheshireCat
from cat.types import (
    ChatRequest,
    ChatResponse,
)
from cat.auth import User

from .llm import LLMMixin
from .stream import EventStreamMixin

class CatMixin(LLMMixin, EventStreamMixin):
    """
    Mixin for shared methods between StrayCat and BaseAgent.
    Provides access to chat request/response, user info, and core subsystems.
    """

    async def init_mixin(
        self,
        ccat: CheshireCat,
        user: User,
        chat_request: ChatRequest = ChatRequest(),
        chat_response: ChatResponse = ChatResponse(),
        stream_callback: Callable = lambda x: None
    ):
        """Initialize mixin with user, CheshireCat instance,
        chat context, stream callback and plugin defined properties."""
        
        self.ccat = ccat
        self.user = user
        self.chat_request = chat_request
        self.chat_response = chat_response
        self.stream_callback = stream_callback

        # plugins can attach properties to stray and agents
        plugin_extensions = await self.execute_hook(
            "cat_mixin", {}
        )

        for pe_name, pe_value in plugin_extensions.items():
            if hasattr(self, pe_name):
                log.warning(f"Attribute {pe_name} already exists in CatMixin. Skipping.")
            else:
                setattr(self, pe_name, pe_value)


    async def execute_hook(self, hook_name, default_value):
        """Execute a plugin hook."""
        return await self.mad_hatter.execute_hook(
            hook_name,
            default_value,
            self
        )

    async def get_agent(self, slug):
        """
        Get an agent by its slug.
        It is initialized with references to ccat and the current user and chat.
        Returns a copy to avoid instance pollution.
        """
        
        agent = self.ccat.agents.get(slug)
        if not agent:
            raise Exception(f'Agent "{slug}" not found')
        
        agent_copy = deepcopy(agent)
        await agent_copy.init_mixin(
            ccat=self.ccat,
            user=self.user,
            chat_request=self.chat_request,
            chat_response=self.chat_response,
            stream_callback=self.stream_callback
        )
        agent_copy.slug = slug
        return agent_copy

    @property
    def user_id(self) -> str:
        """The user's id. Complete user object is under `self.user`."""
        return self.user.id

    @property
    def mad_hatter(self):
        """Gives access to the `MadHatter` plugin manager."""
        return self.ccat.mad_hatter
    
    @property
    def plugin(self):
        """Access plugin object (used from within a plugin)."""
        return self.ccat.plugin
    
    @property
    def mcpqqqqq(self):
        """Gives access to the MCP client for this user/session."""
        return self._mcp