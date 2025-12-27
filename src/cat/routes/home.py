from fastapi import APIRouter, Body, Request, HTTPException

from typing import List, Dict
from pydantic import BaseModel, Field

from cat.types import Task, TaskResult
from cat.auth import AuthResource, AuthPermission, get_user, get_ccat
from cat.looking_glass import prompts
from cat.protocols.model_context.server import MCPServer
from cat.protocols.agui.streaming import AGUIStream
from cat.types import Message

router = APIRouter(prefix="", tags=["Home"])

class ChatRequest(Task):

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

    mcps: List[MCPServer] = Field(
        default_factory=list,
        description="List of MCP servers the agent will interact with."
    )

    stream: bool = Field(
        True,
        description="Whether to enable streaming tokens or not."
    )

    custom: Dict = Field(
        default_factory=dict,
        description="Dictionary to hold extra custom data."
    )

      
@router.post("/message")
async def message(
    http_request: Request,
    chat_request: ChatRequest = Body(
        ...,
        example={
            "agent": "default",
            "model": "openai:gpt-4o",
            "system_prompt": "You are the Cheshire Cat, and always talk in rhymes.",
            "messages": [
                {
                    "role": "user",
                    "content": {"type": "text", "text": "Meow!"}
                }
            ],
            "stream": False,
        }
    ),
    _ = get_user(AuthResource.CHAT, AuthPermission.EDIT),
    ccat = get_ccat(),
) -> TaskResult:
    """
    Send a message to the Cat. Allows choosing agent, model, system prompt and MCPs.
    """

    # Store chat_request in request.state for access in downstream services
    http_request.state.chat_request = chat_request

    # Get agent from factory
    agent = await ccat.factory.get(
        "agents",
        chat_request.agent,
        request=http_request,
        raise_error=False
    )
    if agent is None:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{chat_request.agent}' not found."
        )

    task = Task(
        messages=chat_request.messages,
        resources=chat_request.resources
    )

    if chat_request.stream:
        return AGUIStream(agent, task).stream()
    else:
        return await agent(task)
