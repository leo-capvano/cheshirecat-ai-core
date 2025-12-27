from typing import Dict, TYPE_CHECKING
from pydantic import Field, BaseModel
from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import ValidationError

from cat import log
from cat.auth.permissions import (
    AuthPermission, AuthResource, get_ccat, get_user, User
)

if TYPE_CHECKING:
    from cat.looking_glass.cheshire_cat import CheshireCat

router = APIRouter(prefix="/me", tags=["User"])

class UserSettings(BaseModel):
    """User settings with schemas from all request services."""
    value: dict
    schemas: dict = Field(default_factory=dict)

@router.get("/settings")
async def get_user_settings(
    r: Request,
    user: User = get_user(AuthResource.CHAT, AuthPermission.READ),
    ccat: "CheshireCat" = get_ccat()
) -> UserSettings:
    """
    Get user settings with schemas from all request services.
    Returns namespaced settings and schemas for each request service.
    """

    # Get current values (already namespaced)
    values = await user.load_settings()
    log.critical(values)

    # Collect schemas from ALL request services (across all plugins)
    schemas = {}
    for service_type, service_dict in ccat.factory.class_index.items():
        for slug, ServiceClass in service_dict.items():
            if ServiceClass.lifecycle == "request":
                log.error(ServiceClass)
                namespace = f"{service_type}_{slug}"
                log.error(namespace)

                # Get instance (pass request for request-scoped services)
                instance = await ccat.factory.get(
                    service_type,
                    slug,
                    request=r
                )

                # Get schema
                model = await instance.settings_model()
                if model:
                    schemas[namespace] = model.model_json_schema()

    return UserSettings(
        value=values,
        schemas=schemas
    )


@router.patch("/settings")
async def patch_user_settings(
    r: Request,
    payload: Dict = Body({"agent_default": {"model": "openai:gpt-4o"}}),
    user: User = get_user(AuthResource.CHAT, AuthPermission.EDIT),
    ccat: "CheshireCat" = get_ccat()
) -> UserSettings:
    """
    Patch user settings (validates each namespace against service schemas).
    Payload should be a dict where keys are namespaces like "agent_default"
    and values are the settings for that service.
    This merges with existing settings - only specified namespaces are updated.
    """

    # Validate each namespace against its service schema
    for namespace, settings in payload.items():
        # Parse namespace
        if "_" not in namespace:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid namespace format: {namespace}"
            )

        parts = namespace.split("_", 1)
        if len(parts) < 2:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid namespace format: {namespace}"
            )

        service_type = parts[0]
        slug = parts[1]

        # Get service class
        service_class = ccat.factory.registry.get(service_type, slug)
        if not service_class:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown service: {namespace}"
            )

        # Verify it's a request service (only request services have user settings)
        if service_class.lifecycle != "request":
            raise HTTPException(
                status_code=400,
                detail=f"Service {namespace} is not a request service"
            )

        # Validate against schema
        instance = await ccat.factory.get(service_type, slug, request=r)
        model = await instance.settings_model()
        if model:
            try:
                model.model_validate(settings)
            except ValidationError as e:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "namespace": namespace,
                        "errors": e.errors()
                    }
                )

    # Load existing settings and merge with payload
    existing_settings = await user.load_settings()
    existing_settings.update(payload)

    # Save merged settings to user
    await user.save_settings(existing_settings)

    # Get schemas for response
    schemas = {}
    for service_type, service_dict in ccat.factory.class_index.items():
        for slug, service_class in service_dict.items():
            if service_class.lifecycle == "request":
                namespace = f"{service_type}_{slug}"
                instance = await ccat.factory.get(
                    service_type,
                    slug,
                    request=r
                )
                model = await instance.settings_model()
                if model:
                    schemas[namespace] = model.model_json_schema()

    return UserSettings(
        value=existing_settings,
        schemas=schemas
    )
