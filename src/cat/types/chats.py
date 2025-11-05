from typing import List
from pydantic import BaseModel

from cat.looking_glass import prompts
from cat.protocols.model_context.type_wrappers import Resource
from cat.protocols.model_context.server import MCPServer

from .messages import Message
from ..protocols.model_context.type_wrappers import TextContent


class ChatRequest(BaseModel):

    agent: str = "default" # name of the agent to run.
    model: str = "default" # e.g. "openai:gpt-5"

    system_prompt: str = prompts.MAIN_PROMPT_PREFIX
    resources: List[Resource] = []
    mcps: List[MCPServer] = []

    messages: List[Message] = [
        Message(
            role="user",
            content=TextContent(
                type="text",
                text="Meow"
            )
        )
    ]

    stream: bool = True # whether to stream tokens or not


class ChatResponse(BaseModel):
    messages: List[Message] = []