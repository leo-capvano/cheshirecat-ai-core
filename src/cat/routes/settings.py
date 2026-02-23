from typing import Dict, List
from pydantic import BaseModel, Field, ValidationError
from fastapi import APIRouter, Request, HTTPException, Body, Query

from cat.auth import AuthPermission, AuthResource, get_user
from cat import log

router = APIRouter(prefix="/settings", tags=["Settings"])


class SettingsEntry(BaseModel):
    """A single service's settings entry."""
    slug: str
    type: str
    name: str
    plugin_id: str | None
    settings: dict
    schema_: dict | None = Field(None, alias="schema")

    model_config = {"populate_by_name": True}


@router.get("")
async def list_settings(
    r: Request,
    type: str | None = Query(None, description="Filter by service type"),
    plugin_id: str | None = Query(None, description="Filter by plugin ID"),
    user=get_user(AuthResource.PLUGIN, AuthPermission.READ),
) -> List[SettingsEntry]:
    """
    List all services that have settings, with metadata, current values, and schemas.
    Supports filtering by service type and/or plugin_id.
    """
    ccat = r.app.state.ccat
    factory = ccat.factory

    entries = []
    for service_type, service_dict in factory.class_index.items():
        # Apply type filter
        if type is not None and service_type != type:
            continue

        for slug, ServiceClass in service_dict.items():
            # Apply plugin_id filter
            if plugin_id is not None and ServiceClass.plugin_id != plugin_id:
                continue

            # Check if service has settings (nested Settings class or settings_model)
            has_nested = ServiceClass.get_settings_schema() is not None

            # Get instance to check settings_model() (may be dynamic)
            try:
                if ServiceClass.lifecycle == "request":
                    instance = await factory.get(service_type, slug, request=r)
                else:
                    instance = await factory.get(service_type, slug)
            except Exception as e:
                log.error(f"Error getting service {service_type}:{slug} for settings: {e}")
                continue

            model = await instance.settings_model()
            if model is None and not has_nested:
                continue

            settings_schema = model.model_json_schema() if model else None
            current_settings = await instance.load_settings()

            entries.append(SettingsEntry(
                slug=slug,
                type=service_type,
                name=ServiceClass.name or ServiceClass.__name__,
                plugin_id=ServiceClass.plugin_id,
                settings=current_settings,
                schema=settings_schema,
            ))

    return entries


@router.put("/{type}/{slug}")
async def update_settings(
    type: str,
    slug: str,
    r: Request,
    payload: Dict = Body(...),
    user=get_user(AuthResource.PLUGIN, AuthPermission.EDIT),
) -> SettingsEntry:
    """
    Save settings for a single service identified by type and slug.
    Validates against schema, saves to DB, triggers service refresh.
    """
    ccat = r.app.state.ccat
    factory = ccat.factory

    # Look up the service class
    ServiceClass = factory.class_index.get(type, {}).get(slug)
    if ServiceClass is None:
        raise HTTPException(
            status_code=404,
            detail=f"Service {type}:{slug} not found"
        )

    # Get instance
    try:
        if ServiceClass.lifecycle == "request":
            instance = await factory.get(type, slug, request=r)
        else:
            instance = await factory.get(type, slug)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Get settings model for validation
    settings_model = await instance.settings_model()
    if settings_model is None:
        raise HTTPException(
            status_code=400,
            detail=f"Service {type}:{slug} does not support settings"
        )

    # Validate
    try:
        validated = settings_model.model_validate(payload)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.errors())

    # Save
    try:
        saved = await instance.save_settings(validated)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {e}")

    # Trigger service refresh
    await ccat.mad_hatter.refresh_caches()

    return SettingsEntry(
        slug=slug,
        type=type,
        name=ServiceClass.name or ServiceClass.__name__,
        plugin_id=ServiceClass.plugin_id,
        settings=saved,
        schema=settings_model.model_json_schema(),
    )
