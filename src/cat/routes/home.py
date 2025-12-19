import json
from fastapi import APIRouter, Body, Request
from fastapi.responses import StreamingResponse

from typing import List, Dict
from pydantic import BaseModel, Field

from cat.auth import AuthResource, AuthPermission, get_user, get_ccat
from cat.looking_glass import prompts
from cat.protocols.model_context.server import MCPServer
from cat.types import Message, TextContent, Resource

router = APIRouter(prefix="", tags=["Home"])

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
    user = get_user(AuthResource.CHAT, AuthPermission.EDIT),
    ccat = get_ccat(),
) -> ChatResponse:

    # Get agent from factory
    agent = await ccat.factory.get_service(
        service_type="agent",
        slug=chat_request.agent,
        request=http_request,
        raise_error=True
    )

    # TODOV2: The queue/stream pattern will be implemented separately
    # For now, use the agent directly
    if chat_request.stream:
        async def event_stream():
            # TODOV2: Replace with queue pattern when implemented
            async for msg in agent.stream(chat_request):
                yield f"data: {json.dumps(dict(msg))}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    else:
        return await agent(chat_request)
