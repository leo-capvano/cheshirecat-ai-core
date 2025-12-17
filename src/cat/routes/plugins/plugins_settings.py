

from typing import Dict
from pydantic import BaseModel, Field, ValidationError
from fastapi import Body, APIRouter, HTTPException
from cat.auth import AuthPermission, AuthResource, check_permissions

router = APIRouter(prefix="/plugins")

class PluginSettings(BaseModel):
    id: str
    value: dict
    schema_: dict = Field(..., alias="schema")

@router.get("/{id}/settings")
async def get_plugin_settings(
    id: str,
    ctx=check_permissions(AuthResource.PLUGIN, AuthPermission.READ),
) -> PluginSettings:
    """Returns the settings of a specific plugin."""

    ccat = ctx.ccat

    if not ccat.mad_hatter.plugin_exists(id):
        raise HTTPException(status_code=404, detail="Plugin not found")

    try:
        plugin = ccat.mad_hatter.plugins[id]
        settings = await plugin.load_settings()
        # settings_model can be sync or async
        model = plugin.settings_model()
        schema = model.model_json_schema()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return PluginSettings(
        id=id,
        value=settings,
        schema=schema
    )


@router.put("/{id}/settings")
async def upsert_plugin_settings(
    id: str,
    payload: Dict = Body({"setting_a": "some value", "setting_b": "another value"}),
    ctx=check_permissions(AuthResource.PLUGIN, AuthPermission.EDIT),
) -> PluginSettings:
    """Updates the settings of a specific plugin (full replacement, not partial)"""

    ccat = ctx.ccat

    if not ccat.mad_hatter.plugin_exists(id):
        raise HTTPException(status_code=404, detail="Plugin not found")

    # Get the plugin object
    plugin = ccat.mad_hatter.plugins[id]

    try:
        from cat import utils

        # Load the plugin settings Pydantic model (sync or async)
        PluginSettingsModel = plugin.settings_model()

        # Validate the settings
        validated_settings = PluginSettingsModel.model_validate(payload)

        # Save settings (full replacement) - save_settings handles BaseModel conversion
        final_settings = await plugin.save_settings(validated_settings)
    except ValidationError as e:
        raise HTTPException(
            status_code=400,
            detail=e.errors()
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    await ccat.mad_hatter.refresh_caches()

    return PluginSettings(
        id=id,
        value=final_settings,
        schema=PluginSettingsModel.model_json_schema()
    )