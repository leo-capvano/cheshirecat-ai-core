from typing import List, Dict
from inspect import isclass

from pydantic import BaseModel, Field
from fastapi import APIRouter, Body, Request, HTTPException

from cat.auth import AuthPermission, AuthResource, get_user, get_ccat
from cat.types import Task, TaskResult
from cat.looking_glass import prompts
from cat.protocols.model_context.server import MCPServer
from cat.protocols.agui.streaming import AGUIStream


router = APIRouter(prefix="/agents", tags=["Agents"])


class ChatRequest(Task):

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

    args: Dict = Field(
        default_factory=dict,
        description="Runtime parameters for the agent. Validated against the agent's ArgsSchema when defined."
    )


class AgentCard(BaseModel):
    slug: str
    name: str | None
    description: str | None
    plugin_id: str | None
    args_schema: dict | None = None


@router.get("")
async def list_agents(
    ccat=get_ccat(),
    _=get_user(AuthResource.CHAT, AuthPermission.READ),
) -> List[AgentCard]:
    """List all registered agents with full details."""

    agents = []
    for slug, Cls in ccat.factory.class_index.get("agents", {}).items():
        args_schema = None
        ArgsSchema = getattr(Cls, 'ArgsSchema', None)
        if ArgsSchema is not None and isclass(ArgsSchema) and issubclass(ArgsSchema, BaseModel):
            args_schema = ArgsSchema.model_json_schema()

        agents.append(AgentCard(
            slug=slug,
            name=Cls.name or Cls.__name__,
            description=Cls.description,
            plugin_id=Cls.plugin_id,
            args_schema=args_schema,
        ))
    return agents


@router.post("/{slug}/message")
async def agent_message(
    slug: str,
    http_request: Request,
    chat_request: ChatRequest = Body(
        ...,
        openapi_examples={
            "simple": {
                "summary": "Simple text message",
                "value": {
                    "model": "openai:gpt-4o",
                    "system_prompt": "You are the Cheshire Cat, and always talk in rhymes.",
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": "Meow!"}]
                        }
                    ],
                    "stream": False,
                }
            },
            "with_args": {
                "summary": "Message with agent args",
                "value": {
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": "Hello!"}]
                        }
                    ],
                    "args": {"temperature": 0.5},
                }
            }
        }
    ),
    _=get_user(AuthResource.CHAT, AuthPermission.EDIT),
    ccat=get_ccat(),
) -> TaskResult:
    """Send a message to a specific agent identified by its slug."""

    http_request.state.chat_request = chat_request

    agent = await ccat.factory.get(
        "agents",
        slug,
        request=http_request,
        raise_error=False
    )
    if agent is None:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{slug}' not found."
        )

    task = Task(
        messages=chat_request.messages,
        resources=chat_request.resources
    )

    if chat_request.stream:
        return AGUIStream(agent, task).stream()
    else:
        return await agent(task)
