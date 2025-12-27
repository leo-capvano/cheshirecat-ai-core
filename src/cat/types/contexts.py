from typing import TYPE_CHECKING
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from cat.mad_hatter.decorators import Tool
    from .tasks import Task, TaskResult


class Context(BaseModel):
    """Model context containing relevant information for generation."""

    model_config = ConfigDict(
        extra="allow",
        arbitrary_types_allowed=True,
    )

    system_prompt: str
    """The system prompt"""

    task: "Task"
    """The current task being processed."""

    result: "TaskResult"
    """The result of the task so far."""

    tools: list["Tool"]
    """Available tools for the model to use."""
    
