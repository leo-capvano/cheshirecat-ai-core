from typing import List, Literal

from pydantic import BaseModel

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage
)

from ..protocols.model_context.type_wrappers import TextContent, ContentBlock


class Message(BaseModel):
    """Single message exchanged between user and assistant, part of a conversation."""

    role: Literal["user", "assistant", "tool"]
    content : ContentBlock

    # only populated if the LLM wants to use a tool (role "assistant")
    # role "tool" is only used for tool output, to update message list
    tool_calls : List[dict] = []

    def langchainfy(self):
        # TODOV2: should convert for every mcp ContentBlock type
        if self.role == "user":
            return HumanMessage(
                content=self.content.text
            )
        elif self.role == "assistant":
            return AIMessage(
                content=self.content.text,
                tool_calls=self.tool_calls
            )
        elif self.role == "tool":
            return ToolMessage(
                content=self.content.tool["out"],
                tool_call_id=self.content.tool["in"]["id"],
                name=self.content.tool["in"]["name"]
            )
        else:
            raise Exception
    
    @classmethod
    def from_langchain(cls, langchain_msg):
        # assuming it is always an AIMessage
        tool_calls = []
        text = langchain_msg.content
        if hasattr(langchain_msg, "tool_calls") \
            and len(langchain_msg.tool_calls) > 0:
            
            tool_calls = langchain_msg.tool_calls
            # Otherwise empty
            text = str(langchain_msg.tool_calls)
            
        return cls(
            role="assistant",
            tool_calls=tool_calls,
            content=TextContent(
                type="text", # assuming LLM output is text only
                text=text,
            )
        )


