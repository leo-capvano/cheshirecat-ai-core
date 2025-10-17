from typing import List

from cat.types import Message, Context
from cat.auth.permissions import AuthResource
from cat.db.models import ContextDB
from .common.crud import create_crud
from .common.schemas import CRUDSelect, CRUDUpdate

class ChatSelect(CRUDSelect):
    messages: List[Message]

class ContextCreateUpdate(CRUDUpdate, Context):
    pass

class ContextSelect(CRUDSelect, ContextCreateUpdate):
    chats: List[ChatSelect] = []

router = create_crud(
    db_model=ContextDB,
    prefix="/contexts",
    tag="Contexts",
    auth_resource=AuthResource.CHAT,
    restrict_by_user_id=True,
    search_fields=["name", "instructions", "resources"],
    select_schema=ContextSelect,
    create_schema=ContextCreateUpdate,
    update_schema=ContextCreateUpdate
)

