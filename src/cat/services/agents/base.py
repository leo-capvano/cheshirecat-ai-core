from typing import List, TYPE_CHECKING

from cat.types import Message, Context, Task, TaskResult
from cat.mad_hatter.decorators import Tool

from ..service import RequestService

if TYPE_CHECKING:
    from cat.base import Directive


class Agent(RequestService):

    service_type = "agents"
    system_prompt = "You are an Agent in the Cheshire Cat AI fleet. Help the user and other agents with their requests."
    model = None # can be a slug like "openai:gpt-4o", if None will be taken from request or settings

    directives: List["Directive"] = []

    async def __call__(self, task: Task) -> TaskResult:
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

        async with self.ccat.mcp_clients.get_user_client(self) as mcp_client:
            self.mcp = mcp_client
            
            self.ctx = Context(
                system_prompt = await self.get_system_prompt(),
                task = task,
                result = TaskResult(),
                tools = await self.list_tools()
            )
            
            self.ctx = await self.execute_hook(
                "before_agent_execution", self.ctx
            )
            self.ctx = await self.execute_hook(
                f"before_{self.slug}_agent_execution", self.ctx
            )
            
            # agentic loop
            await self.loop()
            
            self.ctx = await self.execute_hook(
                f"after_{self.slug}_agent_execution", self.ctx
            )
            self.ctx = await self.execute_hook(
                "after_agent_execution", self.ctx
            )

        return self.ctx.result

    async def loop(self):
        """
        Agentic loop.
        Runs LLM generations and tool calls until the LLM stops generating tool calls.
        Updates chat response in place.
        """

        while True:
            
            # let directives work on the context
            for d in self.directives:
                tmp_ctx = await d.step(self.ctx)
                if tmp_ctx is not None and isinstance(tmp_ctx, Context):
                    self.ctx = tmp_ctx

            llm_mex: Message = await self.llm(
                # prompt construction
                self.ctx.system_prompt,
                # pass conversation messages
                messages=self.ctx.task.messages + self.ctx.result.messages,
                # pass tools
                tools=self.ctx.tools,
                # whether to stream or not
                stream=self.request.stream
            )

            self.ctx.result.messages.append(llm_mex)
            
            if len(llm_mex.tool_calls) == 0:
                # No tool calls, exit
                return
            else:
                # LLM has chosen to use tools, run them
                for tool_call in llm_mex.tool_calls:
                    # actually executing the tool
                    tool_message = await self.call_tool(tool_call)
                    # append tool message
                    self.ctx.result.messages.append(tool_message)

            self.ctx.step_number += 1

    async def get_system_prompt(self) -> str:
        """
        Build the system prompt.
        Base method delegates prompt construction to hooks.
        Prompt is built in two parts: prefix and suffix.
        Prefix is the main prompt, suffix can be used to append extra instructions and context (i.e. RAG).
        Override for custom behavior.
        """

        # Get base prompt from self.system_prompt or http request override
        prompt = getattr(self.request, "system_prompt", self.system_prompt)

        prompt = await self.execute_hook(
            "agent_prompt_prefix",
            prompt
        )
        prompt = await self.execute_hook(
            f"agent_{self.slug}_prompt_prefix",
            prompt
        )
        prompt_suffix = await self.execute_hook(
            "agent_prompt_suffix", ""
        )
        prompt_suffix = await self.execute_hook(
            f"agent_{self.slug}_prompt_suffix",
            prompt_suffix
        )

        return prompt + prompt_suffix

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

    async def call_agent(self, slug, task: Task) -> TaskResult:
        """
        Call an agent by its slug. Shortcut for:
        ```python
        a = self.get_agent("my_agent")
        result = await a(task)
        ```
        """
        
        agent = self.factory.get(
            "agents",
            slug,
            request=self.request,
            raise_error=True
        )
        return await agent(task)

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
