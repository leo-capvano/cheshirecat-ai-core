from typing import List
from importlib import metadata
from pydantic import BaseModel

from fastapi import APIRouter, Request

from cat.auth.permissions import AuthPermission, AuthResource, check_permissions

router = APIRouter(prefix="/status", tags=["Status"])


class StatusResponse(BaseModel):
    status: str
    version: str
    auth_handlers: List[str]

class FactoryStatusResponse(BaseModel):
    llms: List[str]
    embedders: List[str]
    agents: List[str]
    mcps: List[str]


@router.get("")
async def status(
    r: Request
) -> StatusResponse:
    """Server status"""

    ccat = r.app.state.ccat

    return StatusResponse(
        status = "We're all mad here, dear!",
        version = metadata.version("cheshire-cat-ai"),
        auth_handlers=ccat.auth_handlers.keys(),
    )


@router.get("/factory")
async def factory_status(
    r: Request,
    cat=check_permissions(AuthResource.CHAT, AuthPermission.READ),
) -> FactoryStatusResponse:
    """Available factory objects (llms, agents, auth handlers etc)."""

    ccat = r.app.state.ccat

    return FactoryStatusResponse(
        llms=ccat.llms.keys(),
        embedders=ccat.embedders.keys(),
        agents=ccat.agents.keys(),
        mcps=ccat.mcps.keys()
    )


