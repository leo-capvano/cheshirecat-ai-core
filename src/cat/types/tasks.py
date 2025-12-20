from typing import List
from pydantic import BaseModel, Field

from .messages import Message
from cat.protocols.model_context.type_wrappers import Resource


class Task(BaseModel):
    """
    Input for agents.
    Agents receive a Task and return a TaskResult.
    Contains messages (conversation) and resources (context/data).
    """

    messages: List[Message] = Field(
        default_factory=list,
        description="List of messages for the agent."
    )

    resources: List[Resource] = Field(
        default_factory=list,
        description="List of resources (documents, context, data)"
    )

    #custom: Dict[str, Any] = Field(
    #    default_factory=dict,
    #    description="Extra metadata or custom fields"
    #)

class TaskResult(Task):
    """
    Output from an Agent.
    """

    pass
    #status: Literal[]
