from typing import List, TYPE_CHECKING

from cat.mixin.llm import LLMMixin
from cat.mixin.stream import EventStreamMixin
from cat.types import Message, Task, TaskResult

if TYPE_CHECKING:
    from cat.mad_hatter.decorators import Tool

from ..service import RequestService

class Agent(RequestService, LLMMixin, EventStreamMixin):

    service_type = "agent"
    system_prompt = "You are an Agent in the Cheshire Cat AI fleet. Help the user and other agents with their requests."
    model = None # can be a slug like "openai:gpt-4o", if None will be taken from request or settings

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

        self.task = task
        self.result = TaskResult()

        # TODOV2: add agent_fast_reply hook
        async with self.ccat.mcp_clients.get_user_client(self) as mcp_client:
            self.mcp = mcp_client
            
            self.task = await self.execute_hook(
                "before_agent_execution", self.task
            )
            self.task = await self.execute_hook(
                f"before_{self.slug}_agent_execution", self.task
            )
            
            await self.execute()
            
            self.result = await self.execute_hook(
                f"after_{self.slug}_agent_execution", self.result
            )
            self.result = await self.execute_hook(
                "after_agent_execution", self.result
            )

        return self.result
        
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
                messages=self.task.messages + self.result.messages,
                # pass tools (global, internal and MCP)
                tools=await self.list_tools(),
                # whether to stream or not
                stream=self.request.stream
            )

            self.result.messages.append(llm_mex)
            
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
                    self.result.messages.append(tool_message)
                    # if t.return_direct: TODOV2 recover return_direct

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

    def get_agent(self, slug) -> "Agent":
        """
        Get an agent by its slug.
        Every call to this method returns a new instance.
        """

        return self.factory.get_service("agent", slug, request=self.request, raise_error=True)
    
    async def call_agent(self, slug, task: Task) -> TaskResult:
        """
        Call an agent by its slug. Shortcut for:
        ```python
        a = self.get_agent("my_agent")
        result = await a(task)
        ```
        """
        
        agent = self.get_agent(slug)
        return await agent(task)

