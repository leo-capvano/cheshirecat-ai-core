from typing import List
from pydantic import BaseModel
from fastapi import APIRouter, Request

from cat.auth import AuthPermission, AuthResource, get_user
from cat import log

router = APIRouter(prefix="/models", tags=["Models"])


class ProviderModels(BaseModel):
    slug: str
    llms: List[str]
    embedders: List[str]


class ModelsResponse(BaseModel):
    providers: List[ProviderModels]


@router.get("")
async def list_models(
    r: Request,
    user=get_user(AuthResource.CHAT, AuthPermission.READ),
) -> ModelsResponse:
    """List available LLMs and embedders from all model providers."""

    ccat = r.app.state.ccat
    factory = ccat.factory

    providers = []
    for slug, ProviderClass in factory.class_index.get("model_providers", {}).items():
        try:
            instance = await factory.get("model_providers", slug)
            providers.append(ProviderModels(
                slug=slug,
                llms=instance.list_llms(),
                embedders=instance.list_embedders(),
            ))
        except Exception as e:
            log.error(f"Error loading model provider {slug}: {e}")

    return ModelsResponse(providers=providers)
