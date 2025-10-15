from typing import Dict, List
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from cat.log import log
from cat.mad_hatter.plugin_manifest import PluginManifest
from cat.auth.permissions import AuthPermission, AuthResource, check_permissions

router = APIRouter(prefix="/registry")

@router.get("")
async def get_available_plugins(
    search: str = None,
    cat=check_permissions(AuthResource.PLUGIN, AuthPermission.LIST),
    # author: str = None, to be activated in case of more granular search
    # tag: str = None, to be activated in case of more granular search
) -> List[PluginManifest]:
    """List available plugins"""

    # retrieve plugins from official repo
    registry_plugins = await registry_search_plugins(search)
    # index registry plugins by url
    registry_plugins_index = {}
    for p in registry_plugins:
        registry_plugins_index[p.id] = p

    # get active plugins
    active_plugins = await cat.mad_hatter.get_active_plugins()

    # list installed plugins' manifest
    installed_plugins = []
    for p in cat.mad_hatter.plugins.values():
        # get manifest
        manifest: PluginManifest = deepcopy(
            p.manifest
        )  # we make a copy to avoid modifying the plugin obj
        manifest.local_info["active"] = p.id in active_plugins

        # do not show already installed plugins among registry plugins
        r = registry_plugins_index.pop(manifest.plugin_url, None)
        
        manifest.local_info["upgrade"] = None
        # filter by query
        plugin_text = manifest.model_dump_json()
        if (search is None) or (search.lower() in plugin_text):
            if r is not None:
                if r.version is not None and r.version != p.manifest.version:
                    manifest["upgrade"] = r["version"]
            installed_plugins.append(manifest)

    return installed_plugins + registry_plugins

class PluginRegistryUpload(BaseModel):
    url: str

@router.post("/install")
async def install_plugin_from_registry(
    payload: PluginRegistryUpload,
    cat=check_permissions(AuthResource.PLUGIN, AuthPermission.WRITE),
) -> PluginManifest:
    """Install a new plugin from registry"""

    # download zip from registry
    try:
        tmp_plugin_path = await registry_download_plugin(payload.url)
        plugin = await cat.mad_hatter.install_plugin(tmp_plugin_path)
    except Exception as e:
        log.error("Could not download plugin from registry")
        raise HTTPException(status_code=500, detail="Could not download plugin from registry")

    return manifest # TODO return InstalledPlugin