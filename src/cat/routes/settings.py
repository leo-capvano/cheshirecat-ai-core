from typing import Dict, List
from pydantic import BaseModel, Field, ValidationError
from fastapi import APIRouter, Request, HTTPException, Body

from cat.auth import get_user
from cat import log

router = APIRouter(prefix="/settings", tags=["Settings"])


class SettingsEntry(BaseModel):
    """A single service's settings entry."""
    id: str
    slug: str
    type: str
    name: str
    plugin_id: str | None
    value: dict
    schema_: dict | None = Field(None, alias="schema")

    model_config = {"populate_by_name": True}


def _make_id(plugin_id: str | None, service_type: str, slug: str) -> str:
    return f"{plugin_id}__{service_type}__{slug}"


def _parse_id(id: str) -> tuple[str, str, str]:
    parts = id.split("__")
    if len(parts) != 3:
        raise HTTPException(status_code=404, detail=f"Invalid settings id: {id}")
    return parts[0], parts[1], parts[2]


@router.get("")
async def list_settings(
    r: Request,
    user=get_user("settings:read"),
) -> List[SettingsEntry]:
    """
    List all services that have settings, with metadata, current values, and schemas.
    """
    ccat = r.app.state.ccat

    entries = []
    for service_type, service_dict in ccat.factory.class_index.items():
        for slug, ServiceClass in service_dict.items():
            # Get instance to check settings_model() (the authoritative source)
            try:
                if ServiceClass.lifecycle == "request":
                    instance = await ccat.get(service_type, slug, request=r)
                else:
                    instance = await ccat.get(service_type, slug)
            except Exception as e:
                log.error(f"Error getting service {service_type}:{slug} for settings: {e}")
                continue

            model = await instance.settings_model()
            if model is None:
                continue

            settings_schema = model.model_json_schema()
            current_settings = await instance.load_settings()

            entries.append(SettingsEntry(
                id=_make_id(ServiceClass.plugin_id, service_type, slug),
                slug=slug,
                type=service_type,
                name=ServiceClass.name or ServiceClass.__name__,
                plugin_id=ServiceClass.plugin_id,
                value=current_settings,
                schema=settings_schema,
            ))

    return entries


@router.put("/{id}")
async def update_settings(
    id: str,
    r: Request,
    payload: Dict = Body(...),
    user=get_user("settings:edit"),
) -> SettingsEntry:
    """
    Save settings for a single service identified by its composite id.
    Validates against schema, saves to DB, triggers service refresh.
    """
    plugin_id, service_type, slug = _parse_id(id)

    ccat = r.app.state.ccat

    # Look up the service class
    ServiceClass = ccat.factory.class_index.get(service_type, {}).get(slug)
    if ServiceClass is None or ServiceClass.plugin_id != plugin_id:
        raise HTTPException(
            status_code=404,
            detail=f"Settings {id} not found"
        )

    # Get instance
    try:
        if ServiceClass.lifecycle == "request":
            instance = await ccat.get(service_type, slug, request=r)
        else:
            instance = await ccat.get(service_type, slug)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Get settings model for validation
    settings_model = await instance.settings_model()
    if settings_model is None:
        raise HTTPException(
            status_code=400,
            detail=f"Settings {id} does not support settings"
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
        id=id,
        slug=slug,
        type=service_type,
        name=ServiceClass.name or ServiceClass.__name__,
        plugin_id=ServiceClass.plugin_id,
        value=saved,
        schema=settings_model.model_json_schema(),
    )
