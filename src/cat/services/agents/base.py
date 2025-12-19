from typing import List, Any, TYPE_CHECKING

from cat.mixin.llm import LLMMixin
from cat.mixin.stream import EventStreamMixin
from cat.types import Message, AgentMessage

if TYPE_CHECKING:
    from cat.auth.user import User
    from cat.looking_glass.cheshire_cat import CheshireCat
    from cat.mad_hatter.decorators import Tool

from ..service import RequestService

class Agent(RequestService, LLMMixin, EventStreamMixin):

    service_type = "agent"

    async def __call__(self, request: AgentMessage) -> AgentMessage:
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
        self.response = AgentMessage()

        # TODOV2: add agent_fast_reply hook
        
        # Build HookContext for MCP client (if needed)
        from cat.looking_glass.hook_context import HookContext
        ctx = HookContext(self)
        async with self.ccat.mcp_clients.get_user_client(ctx) as mcp_client:
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

    async def list_tools(self) -> List["Tool"]:
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

    def get_agent(self, slug):
        """
        Get an agent by its slug.
        Every call to this method returns a new instance.
        """

        AgentClass = self.ccat.agents.get(slug)
        if not AgentClass:
            raise Exception(f'Agent "{slug}" not found')

        # Agent is a RequestService, pass ccat and request
        return AgentClass(self.ccat, self.request)
    
    async def call_agent(self, slug, request: AgentMessage) -> AgentMessage:
        """
        Call an agent by its slug. Shortcut for:
        ```python
        a = self.get_agent("my_agent")
        response = await a(request)
        ```
        """
        
        agent = self.get_agent(slug)
        return await agent(request)

