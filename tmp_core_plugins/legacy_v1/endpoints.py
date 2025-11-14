
from typing import Dict

from cat.mad_hatter.decorators import endpoint
from cat.auth import check_permissions, AuthResource, AuthPermission
from cat.utils import BaseModelDict
from .convo import CatMessage

class LegacyHTTPUserMessage(BaseModelDict):
    text: str

# TODOV2: provide legacy support using CatMessage and history stored somewhere??? Or just drop it
@endpoint.post("/message", prefix="", tags=["Legacy"], response_model=CatMessage)
async def message_with_cat(
    user_message_json: LegacyHTTPUserMessage,
    cat=check_permissions(AuthResource.CHAT, AuthPermission.EDIT),
) -> Dict:
    """Get a response from the Cat"""

    return await cat(user_message_json.model_dump())