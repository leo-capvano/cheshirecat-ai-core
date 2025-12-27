from typing import Dict
from pydantic import BaseModel, Field, ValidationError
from fastapi import APIRouter, Request, HTTPException, Body

from cat.auth import AuthPermission, AuthResource, get_user
from cat.services.service import ServiceMetadata
from cat import log

router = APIRouter(prefix="/services", tags=["Services"])


class ServiceDetails(BaseModel):
    """Service details including metadata and current settings."""
    metadata: ServiceMetadata
    settings: dict | None = None


class ServiceSettings(BaseModel):
    """Service settings with schema."""
    service_type: str
    slug: str
    value: dict
    schema_: dict | None = Field(None, alias="schema")


@router.get("")
async def list_services(
    r: Request,
    user = get_user(AuthResource.CHAT, AuthPermission.READ),
) -> Dict[str, Dict[str, ServiceMetadata]]:
    """
    List all available services with their metadata and capabilities.
    Services are organized by type (agent, memory, model_provider, etc).
    """
    ccat = r.app.state.ccat
    factory = ccat.factory

    service_metadata = {}
    for service_type, service_dict in factory.class_index.items():
        service_metadata[service_type] = {}
        for slug, ServiceClass in service_dict.items():
            try:
                # Pass request only for request-scoped services
                if ServiceClass.lifecycle == "request":
                    instance = await factory.get(service_type, slug, request=r)
                else:
                    instance = await factory.get(service_type, slug)
                service_metadata[service_type][slug] = await instance.get_meta()
            except Exception as e:
                log.error(f"Error loading service {service_type}:{slug} - {e}")

    return service_metadata


@router.get("/{service_type}/{slug}")
async def get_service(
    service_type: str,
    slug: str,
    r: Request,
    user = get_user(AuthResource.CHAT, AuthPermission.READ),
) -> ServiceDetails:
    """
    Get details for a specific service including metadata and current settings.
    """
    ccat = r.app.state.ccat
    factory = ccat.factory

    # Check service class lifecycle
    ServiceClass = factory.registry.get(service_type, slug)
    if ServiceClass is None:
        raise HTTPException(
            status_code=404,
            detail=f"Service {service_type}:{slug} not found"
        )

    # Get service instance (pass request for request-scoped services)
    if ServiceClass.lifecycle == "request":
        instance = await factory.get(service_type, slug, request=r)
    else:
        instance = await factory.get(service_type, slug)

    # Get metadata
    metadata = await instance.get_meta()

    # Get current settings
    settings = await instance.load_settings()

    return ServiceDetails(
        metadata=metadata,
        settings=settings
    )


@router.get("/{service_type}/{slug}/settings")
async def get_service_settings(
    service_type: str,
    slug: str,
    r: Request,
    user = get_user(AuthResource.CHAT, AuthPermission.READ),
) -> ServiceSettings:
    """
    Get current settings for a specific service.
    Returns settings value and schema.
    """
    ccat = r.app.state.ccat
    factory = ccat.factory

    # Check service class lifecycle
    ServiceClass = factory.registry.get(service_type, slug)
    if ServiceClass is None:
        raise HTTPException(
            status_code=404,
            detail=f"Service {service_type}:{slug} not found"
        )

    # Get service instance (pass request for request-scoped services)
    if ServiceClass.lifecycle == "request":
        instance = await factory.get(service_type, slug, request=r)
    else:
        instance = await factory.get(service_type, slug)

    # Get settings schema
    settings_model = await instance.settings_model()
    settings_schema = settings_model.model_json_schema() if settings_model else None

    # Load current settings
    current_settings = await instance.load_settings()

    return ServiceSettings(
        service_type=service_type,
        slug=slug,
        value=current_settings,
        schema=settings_schema
    )


@router.put("/{service_type}/{slug}/settings")
async def update_service_settings(
    service_type: str,
    slug: str,
    r: Request,
    payload: Dict = Body(...),
    user = get_user(AuthResource.CHAT, AuthPermission.WRITE),
) -> ServiceSettings:
    """
    Update settings for a specific service (full replacement, not partial).
    Settings are validated against the service's settings schema.
    Only works for singleton services - request-scoped services have transient settings.
    """
    ccat = r.app.state.ccat
    factory = ccat.factory

    # Check service class lifecycle
    ServiceClass = factory.registry.get(service_type, slug)
    if ServiceClass is None:
        raise HTTPException(
            status_code=404,
            detail=f"Service {service_type}:{slug} not found"
        )

    # Get service instance (pass request for request-scoped services)
    if ServiceClass.lifecycle == "request":
        instance = await factory.get(service_type, slug, request=r)
    else:
        instance = await factory.get(service_type, slug)

    # Check if service is request-scoped
    if instance.lifecycle == "request":
        raise HTTPException(
            status_code=400,
            detail=f"Service {service_type}:{slug} is request-scoped and does not support persistent settings"
        )

    # Get settings model
    settings_model = await instance.settings_model()
    if settings_model is None:
        raise HTTPException(
            status_code=400,
            detail=f"Service {service_type}:{slug} does not support settings"
        )

    # Validate settings with Pydantic model
    try:
        validated_settings = settings_model.model_validate(payload)
    except ValidationError as e:
        raise HTTPException(
            status_code=400,
            detail=e.errors()
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    # Save settings (full replacement) - save_settings handles BaseModel conversion
    try:
        final_settings = await instance.save_settings(validated_settings)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save settings: {str(e)}"
        )

    # Trigger refresh to reload services with new settings
    await ccat.mad_hatter.refresh_caches()

    return ServiceSettings(
        service_type=service_type,
        slug=slug,
        value=final_settings,
        schema=settings_schema
    )
