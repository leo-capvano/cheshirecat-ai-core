from typing import List, Dict
from pydantic import BaseModel, Field

from cat.looking_glass import prompts
from cat.protocols.model_context.type_wrappers import Resource
from cat.protocols.model_context.server import MCPServer

from .messages import Message
from ..protocols.model_context.type_wrappers import TextContent


class ChatRequest(BaseModel):

    agent: str = Field(
        "default",
        description="Agent slug, must be one of the available agents."
    )

    model: str = Field(
        "default",
        description='Model slug as defined by plugins, e.g. "openai:gpt-5".'
    )

    system_prompt: str = Field(
        prompts.MAIN_PROMPT_PREFIX,
        description="System prompt (agent prompt prefix) to set the conversation context."
    )

    resources: List[Resource] = Field(
        default_factory=list,
        description="List of user defined resources (usually uploaded files) available to the agent."
    )

    mcps: List[MCPServer] = Field(
        default_factory=list,
        description="List of MCP servers the agent will interact with."
    )

    messages: List[Message] = Field(
        default_factory=lambda: [
            Message(
                role="user",
                content=TextContent(
                    type="text",
                    text="Meow"
                )
            )
        ],
        description="List of chat messages in the conversation."
    )

    stream: bool = Field(
        True,
        description="Whether to enable streaming tokens or not."
    )

    custom: Dict = Field(
        default_factory=dict,
        description="Dictionary to hold extra custom data."
    )


class ChatResponse(BaseModel):
    messages: List[Message] = Field(
        default_factory=list,
        description="List of chat messages returned in the response."
    )
    
    custom: Dict = Field(
        default_factory=dict,
        description="Dictionary to hold extra custom data."
    )