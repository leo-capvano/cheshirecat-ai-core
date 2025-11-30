from typing import List

from cat.types import Message
from cat.mixin.runtime import CatMixin
from cat.mad_hatter.decorators import CatTool

class BaseAgent(CatMixin):

    async def __call__(self):
        """Main entry point for the agent, to run an agent like a function."""

        async with self.ccat.mcp_clients.get_user_client(self) as mcp_client:
            self.mcp = mcp_client
            await self.execute_hook("before_agent_execution", self.chat_request)
            await self.execute_hook(f"before_{self.slug}_agent_execution", self.chat_request)
            await self.execute()
            await self.execute_hook(f"after_{self.slug}_agent_execution", self.chat_response)
            await self.execute_hook("after_agent_execution", self.chat_response) 

    async def execute(self):
        """Agentic loop."""

        while True:
            llm_mex: Message = await self.llm(
                # delegate prompt construction to plugins
                await self.get_system_prompt(),
                # pass conversation messages
                messages=self.chat_request.messages + self.chat_response.messages,
                # pass tools (both internal and MCP)
                tools=await self.list_tools(),
                # whether to stream or not
                stream=self.chat_request.stream,
            )

            self.chat_response.messages.append(llm_mex)
            
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
                    self.chat_response.messages.append(tool_message)

                    # if t.return_direct: TODOV2 recover return_direct

    async def get_system_prompt(self) -> str:
        """Build the system prompt from prefix and suffix hooks."""

        prompt_prefix = await self.execute_hook(
            "agent_prompt_prefix",
            self.chat_request.system_prompt
        )
        prompt_suffix = await self.execute_hook(
            "agent_prompt_suffix", ""
        )

        return prompt_prefix + prompt_suffix

    async def list_tools(self) -> List[CatTool]:
        """Get both plugins' tools and MCP tools in CatTool format."""

        mcp_tools = await self.mcp.list_tools()
        mcp_tools = [
            CatTool.from_fastmcp(t, self.mcp.call_tool)
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
    

    
