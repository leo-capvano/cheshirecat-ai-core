import aiofiles
import mimetypes
from copy import deepcopy
from typing import Dict, List
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, UploadFile
from cat.log import log
from cat.mad_hatter.registry import registry_search_plugins, registry_download_plugin
from cat.auth.permissions import AuthPermission, AuthResource, check_permissions
from cat.mad_hatter.plugin_manifest import PluginManifest

router = APIRouter(prefix="/plugins")


class InstalledPlugin(BaseModel):
    id: str
    active: bool
    manifest: PluginManifest


@router.get("")
async def get_plugins(
    search: str = None,
    cat=check_permissions(AuthResource.PLUGIN, AuthPermission.LIST)
) -> List[InstalledPlugin]:
    """List installed plugins"""

    # get active plugins
    active_plugins = await cat.mad_hatter.get_active_plugins()

    # list installed plugins' manifest
    installed_plugins = []
    for p in cat.mad_hatter.plugins.values():
        # filter by query
        plugin_text = p.manifest.model_dump_json()
        if (search is None) or (search.lower() in plugin_text):
            installed_plugins.append(
                InstalledPlugin(
                    id=p.id,
                    active=p.id in active_plugins,
                    manifest=p.manifest,
                )
            )

    return installed_plugins


@router.get("/{id}")
async def get_plugin(
    id: str,
    cat=check_permissions(AuthResource.PLUGIN, AuthPermission.READ),
) -> InstalledPlugin:
    """Returns information on a single plugin"""

    if not cat.mad_hatter.plugin_exists(id):
        raise HTTPException(status_code=404, detail="Plugin not found")

    active_plugins = await cat.mad_hatter.get_active_plugins()
    plugin = cat.mad_hatter.plugins[id]

    return InstalledPlugin(
        id=plugin.id,
        active=plugin.id in active_plugins,
        manifest=plugin.manifest,
    )


@router.post("")
async def install_plugin(
    file: UploadFile,
    cat=check_permissions(AuthResource.PLUGIN, AuthPermission.WRITE),
) -> InstalledPlugin:
    """Install a new plugin from a zip file"""

    admitted_mime_types = [
        "application/zip", "application/x-tar"
    ]
    content_type = mimetypes.guess_type(file.filename)[0]
    print(content_type)
    if content_type not in admitted_mime_types:
        raise HTTPException(
            status_code=400,
            detail=(
                f'MIME type `{file.content_type}` not supported. '
                f'Admitted types: {", ".join(admitted_mime_types)}. '
            )
        )

    log.info(f"Uploading {content_type} plugin {file.filename}")
    plugin_archive_path = f"/tmp/{file.filename}"
    async with aiofiles.open(plugin_archive_path, "wb+") as f:
        content = await file.read()
        await f.write(content)

    plugin = await cat.mad_hatter.install_plugin(plugin_archive_path)
    active_plugins = await cat.mad_hatter.get_active_plugins()

    return InstalledPlugin(
        id=plugin.id,
        active=plugin.id in active_plugins,
        manifest=plugin.manifest
    )


@router.put("/{id}/toggle", status_code=200)
async def toggle_plugin(
    id: str,
    cat=check_permissions(AuthResource.PLUGIN, AuthPermission.WRITE),
):
    """Enable or disable a single plugin"""

    # check if plugin exists
    if not cat.mad_hatter.plugin_exists(id):
        raise HTTPException(status_code=404, detail="Plugin not found")

    try:
        # toggle plugin
        await cat.mad_hatter.toggle_plugin(id)
    except Exception as e:
        log.error(f"Could not toggle plugin {id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{id}")
async def remove_plugin(
    id: str,
    cat=check_permissions(AuthResource.PLUGIN, AuthPermission.DELETE),
):
    """Physically remove plugin."""

    # check if plugin exists
    if not cat.mad_hatter.plugin_exists(id):
        raise HTTPException(status_code=404, detail="Plugin not found")

    try:
        # remove folder, hooks and tools
        await cat.mad_hatter.uninstall_plugin(id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
