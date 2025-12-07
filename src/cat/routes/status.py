from typing import List, Dict
from importlib import metadata
from pydantic import BaseModel

from fastapi import APIRouter, Request

from cat.auth import AuthPermission, AuthResource, check_permissions
from cat.mad_hatter.decorators import FactoryObjectMetadata

router = APIRouter(prefix="/status", tags=["Status"])


class StatusResponse(BaseModel):
    status: str
    version: str
    auth_handlers: Dict[str, FactoryObjectMetadata]

class FactoryStatusResponse(BaseModel):
    agents: Dict[str, FactoryObjectMetadata]
    models: Dict[str, FactoryObjectMetadata]
    #llms: List[str]
    #embedders: List[str]
    mcps: List[str]


@router.get("")
async def status(
    r: Request
) -> StatusResponse:
    """Server status"""

    ccat = r.app.state.ccat

    auth_handlers = {}
    for slug, ah in ccat.auth_handlers.items():
        auth_handlers[slug] = ah.get_factory_metadata()
        
    return StatusResponse(
        status = "We're all mad here, dear!",
        version = metadata.version("cheshire-cat-ai"),
        auth_handlers=auth_handlers,
    )


@router.get("/factory")
async def factory_status(
    r: Request,
    cat=check_permissions(AuthResource.CHAT, AuthPermission.READ),
) -> FactoryStatusResponse:
    """Available factory objects (llms, agents, auth handlers etc)."""

    ccat = r.app.state.ccat

    agents = {}
    for slug, A in ccat.agents.items():
        agents[slug] = A.get_factory_metadata()

    models = {}
    for slug, vendor in ccat.models.items():
        models[slug] = vendor.get_factory_metadata()
        models[slug].llms = list(vendor.llms.keys())
        models[slug].embedders = list(vendor.embedders.keys())

    return FactoryStatusResponse(
        agents=agents,
        models=models,
        mcps=ccat.mcps.keys()
    )


