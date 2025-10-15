

from typing import Dict
from pydantic import BaseModel, ValidationError
from fastapi import Body, APIRouter, HTTPException
from cat.log import log
from cat.auth.permissions import AuthPermission, AuthResource, check_permissions

router = APIRouter(prefix="/plugins")

@router.get("/{id}/settings")
async def get_plugin_settings(
    id: str,
    cat=check_permissions(AuthResource.PLUGIN, AuthPermission.READ),
) -> Dict:
    """Returns the settings of a specific plugin"""

    if not cat.mad_hatter.plugin_exists(id):
        raise HTTPException(status_code=404, detail="Plugin not found")

    try:
        settings = cat.mad_hatter.plugins[id].load_settings()
        schema = cat.mad_hatter.plugins[id].settings_schema()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if schema["properties"] == {}:
        schema = {}

    return {"id": id, "value": settings, "schema": schema}


@router.put("/{id}/settings")
async def upsert_plugin_settings(
    id: str,
    payload: Dict = Body({"setting_a": "some value", "setting_b": "another value"}),
    cat=check_permissions(AuthResource.PLUGIN, AuthPermission.EDIT),
) -> Dict:
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
    except ValidationError as e:
        raise HTTPException(
            status_code=400,
            detail="\n".join(list(map((lambda x: x["msg"]), e.errors()))), # TODOV2: can be raw JSON
        )

    final_settings = plugin.save_settings(payload)

    return {"id": id, "value": final_settings}