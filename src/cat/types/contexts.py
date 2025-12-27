from __future__ import annotations
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from cat.mad_hatter.decorators import Tool
from .tasks import Task, TaskResult


class Context(BaseModel):
    """Model context containing relevant information for generation."""

    model_config = ConfigDict(
        extra="allow",
        arbitrary_types_allowed=True,
    )

    step_number: int = 0
    """The current step number in the agentic loop."""

    finished: bool = False
    """Whether the task is finished."""

    system_prompt: str
    """The system prompt"""

    task: Task
    """The current task being processed."""

    result: TaskResult
    """The result of the task so far."""

    tools: list[Tool]
    """Available tools for the model to use."""
