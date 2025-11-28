from typing import List
from abc import ABC, abstractmethod

from cat.mixin.runtime import CatMixin
from cat.mad_hatter.decorators import CatTool

class BaseAgent(ABC, CatMixin):

    @abstractmethod
    async def execute(self):
        """Abstract method to implement when creating an agent."""

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
    

    
