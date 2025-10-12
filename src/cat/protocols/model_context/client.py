from cachetools import TTLCache
from slugify import slugify
from fastmcp.client import Client

from cat.log import log


class MCPClient(Client):
    """Cat MCP client is scoped by user_id and does not keep a live connection to servers.
        We use caches waiting for the protocol to become stateless.
    """

    def __init__(self, cat):

        # TODO: get addresses / tokens / api keys from DB
        config = {
            "mcpServers": {}
        }

        for slug, server_config in cat._ccat.mcps:
            config["mcpServers"][slug] = {
                "url": str(server_config.url)
            }

        for url in cat.chat_request.context.mcps:
            slug = slugify(
                str(url).split("://")[1],
                separator="_",
                
            )
            config["mcpServers"][slug] = {
                "url": str(url)
            }

        super().__init__(config)


class MCPClients():
    """Keep a cache of user scoped MCP clients"""

    def __init__(self):
        self.clients = TTLCache(maxsize=1000, ttl=60*10)
    
    def get_user_client(self, cat):
        # TODOV2: check also server config did not change
        if cat.user_id not in self.clients:
            self.clients[cat.user_id] = MCPClient(cat)
        return self.clients[cat.user_id]
    
