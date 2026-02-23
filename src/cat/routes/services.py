from typing import Dict
from fastapi import APIRouter, Request

from cat.auth import AuthPermission, AuthResource, get_user
from cat.services.service import ServiceMetadata
from cat import log

router = APIRouter(prefix="/services", tags=["Services"])


@router.get("")
async def list_services(
    r: Request,
    user=get_user(AuthResource.CHAT, AuthPermission.READ),
) -> Dict[str, Dict[str, ServiceMetadata]]:
    """
    List all available services with their metadata and capabilities.
    Services are organized by type (agent, memory, model_provider, etc).
    Read-only catalog — use /settings endpoints for configuration.
    """
    ccat = r.app.state.ccat
    factory = ccat.factory

    service_metadata = {}
    for service_type, service_dict in factory.class_index.items():
        service_metadata[service_type] = {}
        for slug, ServiceClass in service_dict.items():
            try:
                if ServiceClass.lifecycle == "request":
                    instance = await factory.get(service_type, slug, request=r)
                else:
                    instance = await factory.get(service_type, slug)
                service_metadata[service_type][slug] = await instance.get_meta()
            except Exception as e:
                log.error(f"Error loading service {service_type}:{slug} - {e}")

    return service_metadata
