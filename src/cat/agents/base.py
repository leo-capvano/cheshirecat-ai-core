from typing import List

from cat.auth.user import User
from cat.looking_glass.cheshire_cat import CheshireCat
from cat.types import Message, ChatRequest, ChatResponse
from cat.mixin.llm import LLMMixin
from cat.mixin.stream import EventStreamMixin
from cat.mad_hatter.decorators import Tool, Service
#from cat.looking_glass.stray_cat import StrayCat


class Agent(Service, LLMMixin, EventStreamMixin):

    service_type = "agent"

    def __init__(self, ccat: CheshireCat, user: User, stream_callback):
        self.ccat = ccat
        self.user = user
        self.stream_callback = stream_callback

    async def __call__(self, request: ChatRequest) -> ChatResponse:
        """
        Main entry point for the agent, to run an agent like a function.
        Calls main lifecycle hooks and delegates actual agent logic to `execute()`.
        Sets request and response as instance attributes for easy access within the agent.
        
        Parameters
        ----------
        request : ChatRequest
            ChatRequest object received from the client or from another agent.

        Returns
        -------
        response : ChatResponse
            ChatResponse object, the agent's answer.
        """

        self.request = request
        self.response = ChatResponse()
        
        async with self.ccat.mcp_clients.get_user_client(self) as mcp_client:
            self.mcp = mcp_client
            
            self.request = await self.execute_hook(
                "before_agent_execution", self.request
            )
            self.request = await self.execute_hook(
                f"before_{self.slug}_agent_execution", self.request
            )
            
            await self.execute()
            
            self.response = await self.execute_hook(
                f"after_{self.slug}_agent_execution", self.response
            )
            self.response = await self.execute_hook(
                "after_agent_execution", self.response
            )

        return self.response
        
    async def execute(self):
        """
        Main agent logic, just runs `self.loop()`.
        Override in subclasses for custom behavior.
        """
        await self.loop()

    async def loop(self):
        """
        Agentic loop.
        Runs LLM generations and tool calls until the LLM stops generating tool calls.
        Updates chat response in place.
        """

        while True:
            llm_mex: Message = await self.llm(
                # prompt construction
                await self.get_system_prompt(),
                # pass conversation messages
                messages=self.request.messages + self.response.messages,
                # pass tools (global, internal and MCP)
                tools=await self.list_tools(),
                # whether to stream or not
                stream=self.request.stream,
            )

            self.response.messages.append(llm_mex)
            
            if len(llm_mex.tool_calls) == 0:
                # No tool calls, exit
                return
            else:
                # LLM has chosen to use tools, run them
                # TODOV2: tools may require explicit user permission
                # TODOV2: tools may return an artifact, resource or elicitation
                for tool_call in llm_mex.tool_calls:
                    # actually executing the tool
                    tool_message = await self.call_tool(tool_call)
                    # append tool message
                    self.response.messages.append(tool_message)
                    # if t.return_direct: TODOV2 recover return_direct

    async def get_system_prompt(self) -> str:
        """
        Build the system prompt.
        Base method delegates prompt construction to hooks.
        Prompt is built in two parts: prefix and suffix.
        Prefix is the main prompt, suffix can be used to append extra instructions and context (i.e. RAG).
        Override for custom behavior.
        """

        prompt_prefix = await self.execute_hook(
            "agent_prompt_prefix",
            self.request.system_prompt
        )
        prompt_prefix = await self.execute_hook(
            f"agent_{self.slug}_prompt_prefix",
            prompt_prefix
        )
        prompt_suffix = await self.execute_hook(
            "agent_prompt_suffix", ""
        )
        prompt_suffix = await self.execute_hook(
            f"agent_{self.slug}_prompt_suffix",
            prompt_suffix
        )

        return prompt_prefix + prompt_suffix

    async def list_tools(self) -> List[Tool]:
        """Get plugins' tools, MCP tools, and agent's own tools in CatTool format."""

        # Get MCP tools
        mcp_tools = await self.mcp.list_tools()
        mcp_tools = [
            Tool.from_fastmcp(t, self.mcp.call_tool)
            for t in mcp_tools
        ]

        # Get agent's own tools decorated with @agent_tool
        agent_tools = self.instantiate_agent_tools()

        # Combine all tools
        tools = await self.execute_hook(
            "agent_allowed_tools",
            mcp_tools + self.mad_hatter.tools + agent_tools
        )

        return tools
    
    async def call_tool(self, tool_call, *args, **kwargs):
        """Call a tool."""

        name = tool_call["name"]
        for t in await self.list_tools():
            if t.name == name:
                return await t.execute(self, tool_call)
            
        raise Exception(f"Tool {name} not found")
    
    async def execute_hook(self, hook_name, default_value):
        """Execute a plugin hook."""
        return await self.mad_hatter.execute_hook(
            hook_name,
            default_value,
            self
        )

    def get_agent(self, slug):
        """
        Get an agent by its slug.
        Every call to this method returns a new instance.
        """
        
        AgentClass = self.ccat.agents.get(slug)
        if not AgentClass:
            raise Exception(f'Agent "{slug}" not found')
        
        return AgentClass(
            ccat=self.ccat,
            user=self.user,
            stream_callback=self.stream_callback
        )
    
    async def call_agent(self, slug, request: ChatRequest) -> ChatResponse:
        """
        Call an agent by its slug. Shortcut for:
        ```python
        a = self.get_agent("my_agent")
        response = await a(request)
        ```
        """
        
        agent = self.get_agent(slug)
        return await agent(request)

    def instantiate_agent_tools(self) -> List[Tool]:
        """Find Tool instances on class and bind them to the agent instance."""
        return [
            attr.bind_to(self)
            for name in dir(self.__class__)
            if isinstance(attr := getattr(self.__class__, name, None), Tool)
        ]

    @property
    def plugin(self):
        """Access plugin object (used from within a plugin)."""
        return self.ccat.plugin
    
    @property
    def mcpqqqqq(self):
        """Gives access to the MCP client."""
        return self._mcp

    @property
    def mad_hatter(self):
        """Gives access to the `MadHatter` plugin manager."""
        return self.ccat.mad_hatter
    
    @property
    def user_id(self) -> str:
        """Get the user ID."""
        return self.user.id


    # @property
    # def stream_callback(self):
    #     """Gives access to the stream callback function."""
    #     return self.ctx.stream_callback
