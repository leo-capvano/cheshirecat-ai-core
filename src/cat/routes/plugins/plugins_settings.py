

from typing import Dict
from pydantic import BaseModel, Field, ValidationError
from fastapi import Body, APIRouter, HTTPException
from cat.auth import AuthPermission, AuthResource, get_user, get_ccat

router = APIRouter(prefix="/plugins")

class PluginSettings(BaseModel):
    id: str
    value: dict
    schemas: dict = Field(default_factory=dict)

@router.get("/{id}/settings")
async def get_plugin_settings(
    id: str,
    _ = get_user(AuthResource.PLUGIN, AuthPermission.READ),
    ccat = get_ccat(),
) -> PluginSettings:
    """
    Get plugin settings with schemas from all singleton services in the plugin.
    Returns namespaced settings and schemas for each singleton service.
    """

    if not ccat.mad_hatter.plugin_exists(id):
        raise HTTPException(status_code=404, detail="Plugin not found")

    try:
        plugin = ccat.mad_hatter.plugins[id]

        # Get current values (already namespaced)
        values = await plugin.load_settings()

        # Collect schemas from singleton services in this plugin
        schemas = {}
        for service_class in plugin.services:
            if service_class.lifecycle == "singleton":
                namespace = f"{service_class.service_type}_{service_class.slug}"

                # Get instance
                instance = await ccat.factory.get(
                    service_class.service_type,
                    service_class.slug
                )

                # Get schema
                model = await instance.settings_model()
                if model:
                    schemas[namespace] = model.model_json_schema()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return PluginSettings(
        id=id,
        value=values,
        schemas=schemas
    )


@router.patch("/{id}/settings")
async def patch_plugin_settings(
    id: str,
    payload: Dict = Body({"model_provider_openai": {"api_key": "sk-..."}}),
    _ = get_user(AuthResource.PLUGIN, AuthPermission.EDIT),
    ccat = get_ccat(),
) -> PluginSettings:
    """
    Patch plugin settings (validates each namespace against service schemas).
    Payload should be a dict where keys are namespaces like "model_provider_openai"
    and values are the settings for that service.
    This merges with existing settings - only specified namespaces are updated.
    """

    if not ccat.mad_hatter.plugin_exists(id):
        raise HTTPException(status_code=404, detail="Plugin not found")

    plugin = ccat.mad_hatter.plugins[id]

    try:
        # Validate each namespace against its service schema
        for namespace, settings in payload.items():
            # Parse namespace: "model_provider_openai" -> ("model_providers", "openai")
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

            # Verify service belongs to this plugin
            if service_class.plugin_id != plugin.id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Service {namespace} does not belong to plugin {id}"
                )

            # Validate against schema
            instance = await ccat.factory.get(service_type, slug)
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
        existing_settings = await plugin.load_settings()
        existing_settings.update(payload)

        # Save merged settings to plugin
        await plugin.save_settings(existing_settings)

        # Trigger refresh to reload services with new settings
        await ccat.mad_hatter.refresh_caches()

        # Get updated schemas
        schemas = {}
        for service_class in plugin.services:
            if service_class.lifecycle == "singleton":
                namespace = f"{service_class.service_type}_{service_class.slug}"
                instance = await ccat.factory.get(
                    service_class.service_type,
                    service_class.slug
                )
                model = await instance.settings_model()
                if model:
                    schemas[namespace] = model.model_json_schema()

        return PluginSettings(
            id=id,
            value=existing_settings,
            schemas=schemas
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )