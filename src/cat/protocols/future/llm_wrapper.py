from pydantic import BaseModel

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableConfig
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import StructuredTool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    ToolMessage
)

from cat.types import Message, TextContent
from cat.mad_hatter.decorators import Tool
from cat.env import get_env
from cat import log
from .llm_callbacks import NewTokenHandler


class LLMWrapper:
    """Wraps all langchain stuff in a single place."""

    @classmethod
    async def invoke(
            cls,
            caller,
            model: BaseChatModel,
            system_prompt: str,
            messages: list[Message] = [],
            tools: list[Tool] = [],
            stream: bool = False
        ) -> Message:

        # should we stream the tokens?
        callbacks = []
        if stream:
            callbacks.append(
                NewTokenHandler(caller.agui_event)
            )
            # TODOV2: tool choice tokens are not streamed
        
        # Add callbacks from plugins
        callbacks = await caller.execute_hook(
            "llm_callbacks", callbacks
        )

        log_chat = get_env("CCAT_DEBUG") == "true"
        if(log_chat):
            cls.log_chat_message(system_prompt)
            for m in messages:
                cls.log_chat_message(m)

        # here we deal with motherfucking langchain
        prompt = ChatPromptTemplate(
            messages=[
                SystemMessage(system_prompt)
            ] + [cls.langchainfy_message(m) for m in messages]
        )
        
        llm_with_tools = model.bind_tools([
            cls.langchainfy_tool(t) for t in tools
        ])

        chain = prompt | llm_with_tools
        langchain_msg = await chain.ainvoke(
            {},
            config=RunnableConfig(callbacks=callbacks)
        )
        
        new_mex = cls.from_langchain_message(langchain_msg)

        if(log_chat):
            cls.log_chat_message(new_mex)
            print("-" * 50)
        
        return new_mex

    @classmethod
    def langchainfy_message(cls, message):
        # TODOV2: should convert for every mcp ContentBlock type
        if message.role == "user":
            return HumanMessage(
                content=message.content.text
            )
        elif message.role == "assistant":
            return AIMessage(
                content=message.content.text,
                tool_calls=message.tool_calls
            )
        elif message.role == "tool":
            return ToolMessage(
                content=message.content.text, # TODOV2 handle other blocks,
                tool_call_id=message.content.tool["in"]["id"],
                name=message.content.tool["in"]["name"]
            )
        else:
            raise Exception

    @classmethod
    def from_langchain_message(cls, langchain_msg):
        # assuming it is always an AIMessage
        tool_calls = []
        text = langchain_msg.content
        if hasattr(langchain_msg, "tool_calls") \
            and len(langchain_msg.tool_calls) > 0:
            
            tool_calls = langchain_msg.tool_calls
            # Otherwise empty
            text = "Tool calls:"
            for call in langchain_msg.tool_calls:
                text += f"\t{call['name']} {call['args']}"
            
        return Message(
            role="assistant",
            tool_calls=tool_calls,
            content=TextContent(
                type="text", # assuming LLM output is text only
                text=text,
            )
        )

    @classmethod
    def langchainfy_tool(cls, tool: Tool):
        """Convert Tool to a langchain compatible StructuredTool object"""
        return StructuredTool(
            name=tool.name.strip().replace(" ", "_"),
            description=tool.description,
            args_schema=tool.input_schema,
        )

    @classmethod
    def log_chat_message(cls, message: Message | str):
        
        if(get_env("CCAT_DEBUG") != "true"):
            return
        
        if isinstance(message, str):
            print(
                log.colored_text("instructions".ljust(15), "green")
            )
            print(message)
            
        else:
            print(
                log.colored_text(
                    message.role.ljust(15), "green"
                ),
                end=""
            )
            if isinstance(message.content, list):
                for block in message.content:
                    print(block.text)
            else:
                print(message.content.text)

    # TODOV2: move under LLMMixin and avoid using langchain objects
    @classmethod
    def parse_json(cls, json_string: str, pydantic_model: BaseModel = None) -> dict:
        # instantiate parser
        parser = JsonOutputParser(pydantic_object=pydantic_model)

        # clean to help small LLMs
        replaces = {
            "\\_": "_",
            "\\-": "-",
            "None": "null",
            "{{": "{",
            "}}": "}",
        }
        for k, v in replaces.items():
            json_string = json_string.replace(k, v)

        # first "{" occurrence (required by parser)
        start_index = json_string.index("{")

        # parse
        parsed = parser.parse(json_string[start_index:])

        if pydantic_model:
            return pydantic_model(**parsed)
        return parsed
