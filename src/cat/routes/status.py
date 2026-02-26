from typing import Dict
from importlib import metadata
from pydantic import BaseModel

from fastapi import APIRouter, Request

router = APIRouter(prefix="/status", tags=["Status"])


class AuthHandlerResponse(BaseModel):
    slug: str
    name: str | None
    description: str | None


class StatusResponse(BaseModel):
    status: str
    version: str
    auth_handlers: Dict[str, AuthHandlerResponse]


@router.get("")
async def status(
    r: Request
) -> StatusResponse:
    """Server status"""

    ccat = r.app.state.ccat
    ahs = await ccat.get_auth_handlers()

    return StatusResponse(
        status="We're all mad here, dear!",
        version=metadata.version("cheshire-cat-ai"),
        auth_handlers={
            slug: AuthHandlerResponse(
                slug=ah.slug,
                name=ah.name,
                description=ah.description,
            )
            for slug, ah in ahs.items()
        },
    )


