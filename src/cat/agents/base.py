from typing import List, Any

from cat.types import Message
from cat.agents.bus import AgentBus
from cat.mixin.llm import LLMMixin
from cat.mixin.stream import EventStreamMixin
from cat.mad_hatter.decorators import Tool, FactoryObject

class Agent(FactoryObject, LLMMixin, EventStreamMixin):

    factory_type = "agent"

    def __init__(self, bus: AgentBus):
        self._bus = bus

    async def __call__(self, payload: Any = None) -> Any:
        """
        Main entry point for the agent, to run an agent like a function.
        Calling agent can specify a payload to pass directly.
        """
        
        self.payload = payload
        
        async with self.ccat.mcp_clients.get_user_client(self) as mcp_client:
            self.mcp = mcp_client
            self._bus.request = await self.execute_hook(
                "before_agent_execution", self._bus.request
            )
            self._bus.request = await self.execute_hook(
                f"before_{self.slug}_agent_execution", self._bus.request
            )
            
            out = await self.execute()
            
            self._bus.response = await self.execute_hook(
                f"after_{self.slug}_agent_execution", self._bus.response
            )
            self._bus.response = await self.execute_hook(
                "after_agent_execution", self._bus.response
            )

            return out

    async def execute(self) -> Any:
        """
        Main agent logic, just running a loop over tools and updating ChatResponse.
        Ignores calling agent payload and returns None.
        Override in subclasses for custom behavior.
        """
        await self.inner_loop()

    async def inner_loop(self) -> None:
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
        """Get both plugins' tools and MCP tools in Tool format."""

        mcp_tools = await self.mcp.list_tools()
        mcp_tools = [
            Tool.from_fastmcp(t, self.mcp.call_tool)
            for t in mcp_tools
        ]

        tools = await self.execute_hook(
            "agent_allowed_tools",
            mcp_tools + self.mad_hatter.tools
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
        
        return AgentClass(self._bus)
    
    async def call_agent(self, slug, payload: Any=None) -> Any:
        """
        Call an agent by its slug. Shortcut for:
        ```python
        a = self.get_agent("my_agent")
        await a()
        await a({"foo": "bar"}) # with optional payload
        out = await a()         # in case the agent returns something in .execute()
        ```
        """
        
        agent = self.get_agent(slug)
        return await agent(payload)

    @property
    def plugin(self):
        """Access plugin object (used from within a plugin)."""
        return self._bus.ccat.plugin
    
    @property
    def mcpqqqqq(self):
        """Gives access to the MCP client."""
        return self._mcp
    
    @property
    def ccat(self):
        """Gives access to the CheshireCat instance."""
        return self._bus.ccat

    @property
    def mad_hatter(self):
        """Gives access to the `MadHatter` plugin manager."""
        return self._bus.ccat.mad_hatter
    
    @property
    def user(self):
        """Gives access to the current user."""
        return self._bus.user
    
    @property
    def user_id(self) -> str:
        """Get the user ID."""
        return self._bus.user.id
    
    @property
    def request(self):
        """Gives access to the current ChatRequest."""
        return self._bus.request
    
    @property
    def response(self):
        """Gives access to the current ChatResponse."""
        return self._bus.response
    
    @property
    def stream_callback(self):
        """Gives access to the stream callback function."""
        return self._bus.stream_callback
