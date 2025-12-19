from typing import List, Optional, Dict
from pydantic import BaseModel
import httpx

from fastapi import APIRouter, Query

from cat.auth import AuthPermission, AuthResource, get_user
from cat.routes.common.crud import Page


router = APIRouter(prefix="/registry/public") # TODOV2: find good URL

REGISTRY_URL = "https://registry.modelcontextprotocol.io/v0/servers"

class Transport(BaseModel):
    type: str
    headers: List = []
    url: str | None = None

class RegistryConnector(BaseModel):
    name: str
    description: str
    version: str
    remotes: List[Transport] = []
    meta: Dict = {}

    def supports_http_streaming(self) -> bool:
        for t in self.remotes:
            if "stream" in t.type:
                return True
        return False
    
    def is_latest(self) -> bool:
        return self.meta["io.modelcontextprotocol.registry/official"]["isLatest"]
    
# server status
@router.get("")
async def public_registry(
    search: Optional[str] = Query(None),
    _ = get_user(AuthResource.CONNECTOR, AuthPermission.LIST),
) -> Page[RegistryConnector]:
    """MCP servers available in registry. Only remote ones with http stream transport."""

    async with httpx.AsyncClient() as client:
        res = await client.get(
            REGISTRY_URL,
            params={"search": search, "limit": 100})
    
    raw_servers = res.json()["servers"]
    servers = []
    for rs in raw_servers:
        try:
            rs["meta"] = rs["_meta"]
            server = RegistryConnector(**rs)
            if server.supports_http_streaming() and server.is_latest():
                servers.append(server)
        except Exception:
            pass
    
    return Page(
        items=servers,
        cursor=""
    )