from cat.types import Message

class BaseAgent:
    async def list_tools(self):
        return await self.cat.list_tools()
    
    @property
    def chat_request(self):
        return self.cat.chat_request

class AgentDefault:

    async def execute(self, cat):

        while True:
            llm_mex: Message = await cat.llm(
                # delegate prompt construction to plugins
                await cat.get_system_prompt(),
                # pass conversation messages
                messages=cat.chat_request.messages + cat.chat_response.messages,
                # pass tools (both internal and MCP)
                tools=await cat.list_tools(),
                # whether to stream or not
                stream=cat.chat_request.stream,
            )

            cat.chat_response.messages.append(llm_mex)
            
            if len(llm_mex.tool_calls) == 0:
                # No tool calls, exit
                return
            else:
                # LLM has chosen to use tools, run them
                # TODOV2: tools may require explicit user permission
                # TODOV2: tools may return an artifact, resource or elicitation
                for tool_call in llm_mex.tool_calls:
                    # actually executing the tool
                    tool_message = await cat.call_tool(tool_call)
                    # append tool message
                    cat.chat_response.messages.append(tool_message)

                    # if t.return_direct: TODOV2 recover return_direct