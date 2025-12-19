from typing import List, Dict, Any
from pydantic import BaseModel, Field

from .messages import Message
from cat.protocols.model_context.type_wrappers import Resource


class AgentMessage(BaseModel):
    """
    Input and output message format for agents.
    Agents receive an AgentMessage and return an AgentMessage.
    Contains messages (conversation) and resources (context/data).
    """

    messages: List[Message] = Field(
        default_factory=list,
        description="List of messages in the conversation"
    )

    resources: List[Resource] = Field(
        default_factory=list,
        description="List of resources (documents, context, data)"
    )

    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extra metadata or custom fields"
    )

    class Config:
        arbitrary_types_allowed = True
