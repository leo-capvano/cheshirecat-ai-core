from cat.types import Message
from .base import BaseAgent

class DefaultAgent(BaseAgent):

    async def execute(self):

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