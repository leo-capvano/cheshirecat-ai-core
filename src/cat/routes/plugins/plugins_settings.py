

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
    cat=check_permissions(AuthResource.PLUGIN, AuthPermission.READ),
) -> PluginSettings:
    """Returns the settings of a specific plugin."""

    if not cat.mad_hatter.plugin_exists(id):
        raise HTTPException(status_code=404, detail="Plugin not found")

    try:
        settings = await cat.mad_hatter.plugins[id].load_settings()
        schema = cat.mad_hatter.plugins[id].settings_schema()
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
    cat=check_permissions(AuthResource.PLUGIN, AuthPermission.EDIT),
) -> PluginSettings:
    """Updates the settings of a specific plugin"""

    if not cat.mad_hatter.plugin_exists(id):
        raise HTTPException(status_code=404, detail="Plugin not found")

    # Get the plugin object
    plugin = cat.mad_hatter.plugins[id]

    try:
        # Load the plugin settings Pydantic model
        PluginSettingsModel = plugin.settings_model()
        # Validate the settings
        PluginSettingsModel.model_validate(payload)
        final_settings = await plugin.save_settings(payload)
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
    
    await cat.mad_hatter.refresh_caches()

    return PluginSettings(
        id=id,
        value=final_settings,
        schema=PluginSettingsModel.model_json_schema()
    )