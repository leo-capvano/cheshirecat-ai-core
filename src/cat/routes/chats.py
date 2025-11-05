from typing import List
from uuid import UUID

from cat.types import Message
from cat.auth.permissions import AuthResource
from cat.db.models import ChatDB
from .common.crud import create_crud
from .common.schemas import CRUDSelect, CRUDUpdate


class ChatCreateUpdate(CRUDUpdate):
    messages: List[Message] = []

class ChatSelect(CRUDSelect):
    messages: List[Message]

router = create_crud(
    db_model=ChatDB,
    prefix="/chats",
    tag="Chats",
    auth_resource=AuthResource.CHAT,
    restrict_by_user_id=True,
    search_fields=["name", "messages", "extra"],
    select_schema=ChatSelect,
    create_schema=ChatCreateUpdate,
    update_schema=ChatCreateUpdate
)

