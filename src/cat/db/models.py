from uuid import uuid4
import datetime
from piccolo.table import Table
from piccolo.columns import (
    Varchar,
    JSON,
    UUID,
    Timestamptz,
)

from .database import DB


##############################
### globally scoped tables ###
##############################

class SettingDB(Table, db=DB):
    name = Varchar(length=1000, primary_key=True)
    value = JSON()
    
    class Meta:
        tablename = "ccat_global_settings"


##########################
### user scoped tables ###
##########################

class UserScopedModelDB(Table, db=DB):
    id = UUID(primary_key=True, default=uuid4)
    name = Varchar(length=1000)
    updated_at = Timestamptz(
        auto_update=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    user_id = UUID(index=True)
    extra = JSON()

    class Meta:
        abstract = True


class UserSettingDB(UserScopedModelDB):
    value = JSON()

    class Meta:
        tablename = "ccat_settings"


class ChatDB(UserScopedModelDB):
    messages = JSON()

    class Meta:
        tablename = "ccat_chats"
