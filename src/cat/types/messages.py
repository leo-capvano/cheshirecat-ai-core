from typing import List, Literal, Optional
from pydantic import BaseModel, computed_field

from ..protocols.model_context.type_wrappers import ContentBlock


class Message(BaseModel):
    """Single Message exchanged between user and assistant, part of a conversation."""

    role: Literal["user", "assistant", "tool"]
    content: List[ContentBlock]

    # only populated if the LLM wants to use a tool (role "assistant")
    tool_calls: List[dict] = []

    # only populated for role="tool" messages
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None

    @computed_field
    @property
    def text(self) -> str:
        """Concatenate all text blocks."""
        return "".join(
            block.text for block in self.content
            if hasattr(block, "text")
        )