from typing import List, Literal
from pydantic import BaseModel

from ..protocols.model_context.type_wrappers import ContentBlock


class Message(BaseModel):
    """Single Message exchanged between user and assistant, part of a conversation."""

    role: Literal["user", "assistant", "tool"]
    content : ContentBlock

    # only populated if the LLM wants to use a tool (role "assistant")
    # role "tool" is only used for tool output, to update message list
    tool_calls : List[dict] = []