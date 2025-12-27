from typing import Dict
from importlib import metadata
from pydantic import BaseModel

from fastapi import APIRouter, Request

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
    ahs = await ccat.get_auth_handlers()

    auth_handlers = {}
    for slug, ah in ahs.items():
        auth_handlers[slug] = await ah.get_meta()
        
    return StatusResponse(
        status = "We're all mad here, dear!",
        version = metadata.version("cheshire-cat-ai"),
        auth_handlers=auth_handlers,
    )


