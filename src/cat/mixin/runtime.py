from copy import deepcopy
from typing import Callable

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
        """Initialize mixin with user and CheshireCat instance."""
        
        self.ccat = ccat
        self.user = user
        self.chat_request = chat_request
        self.chat_response = chat_response
        self.stream_callback = stream_callback

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
    
    async def execute_agent(self, slug):

        # get agent by slug
        agent = self.ccat.agents.get(slug)
        if not agent:
            raise Exception(f'Agent "{slug}" not found')
        
        # make a copy of the agent to avoid pollution
        agent_copy = deepcopy(agent)

        # initialize mixin
        await agent_copy.init_mixin(
            ccat=self.ccat,
            user=self.user,
            chat_request=self.chat_request,
            chat_response=self.chat_response,
            stream_callback=self.stream_callback
        )
        
        # run in MCP context
        async with self.ccat.mcp_clients.get_user_client(self) as mcp_client:
            agent_copy.mcp = mcp_client

            # run hooks and agent
            await self.execute_hook("before_agent_execution", agent_copy)
            await self.execute_hook(f"before_{slug}_agent_execution", agent_copy)
            await agent_copy.execute()
            await self.execute_hook(f"after_{slug}_agent_execution", agent_copy)
            await self.execute_hook("after_agent_execution", agent_copy) 

    @property
    def user_id(self) -> str:
        """The user's id. Complete user object is under `self.user`."""
        return self.user.id

    @property
    def _llm(self):
        """Low level LLM instance."""
        slug = self.chat_request.model
        if slug not in self.ccat.llms:
            raise Exception(f'Model "{slug}" not found')
        return self.ccat.llms[slug]

    @property
    def mad_hatter(self):
        """Gives access to the `MadHatter` plugin manager."""
        return self.ccat.mad_hatter
    
    @property
    def plugin(self):
        """Access plugin object (used from within a plugin)."""
        return self.ccat.plugin