from typing import List, Dict
from importlib import metadata
from pydantic import BaseModel

from fastapi import APIRouter, Request

from cat.auth import AuthPermission, AuthResource, check_permissions
from cat.services.service import ServiceMetadata

router = APIRouter(prefix="/status", tags=["Status"])

class StatusResponse(BaseModel):
    status: str
    version: str
    auth_handlers: Dict[str, ServiceMetadata]


@router.get("")
async def status(
    r: Request
) -> StatusResponse:
    """Server status"""

    ccat = r.app.state.ccat

    auth_handlers = {}
    for slug, ah in ccat.auth_handlers.items():
        auth_handlers[slug] = await ah.get_meta()
        
    return StatusResponse(
        status = "We're all mad here, dear!",
        version = metadata.version("cheshire-cat-ai"),
        auth_handlers=auth_handlers,
    )


@router.get("/factory")
async def factory_status(
    r: Request,
    ctx=check_permissions(AuthResource.CHAT, AuthPermission.READ),
) -> Dict[str, Dict[str, ServiceMetadata]]:
    """Available factory objects (llms, agents, auth handlers etc)."""

    services = r.app.state.ccat.services
    service_instances = {}
    for type, service_dict in services.items():
        service_instances[type] = {}
        for slug, ServiceClass in service_dict.items():
            instance = await ServiceClass.get_instance(ctx)
            service_instances[type][slug] = await instance.get_meta()

    return service_instances


