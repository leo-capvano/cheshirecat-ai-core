
from uuid import uuid4

from tortoise import Tortoise, fields
from tortoise.models import Model


##############################
### globally scoped tables ###
########################## ###

class SettingDB(Model):
    name = fields.CharField(primary_key=True, max_length=1000)
    value = fields.JSONField()
    class Meta:
        table = "ccat_global_settings"

"""
class PluginDB(Model):
    name = fields.CharField(primary_key=True, max_length=1000)
    active = fields.BooleanField(default=True)
    settings = fields.JSONField()
    class Meta:
        table = "ccat_global_plugins"
"""

##########################
### user scoped tables ###
##########################

class UserScopedModelDB(Model):
    id = fields.UUIDField(primary_key=True, default=uuid4)
    name = fields.CharField(max_length=1000)
    updated_at = fields.DatetimeField(auto_now=True)
    user_id = fields.UUIDField(db_index=True)
    class Meta:
        abstract = True

class UserSettingDB(UserScopedModelDB):
    value = fields.JSONField()
    class Meta:
        table = "ccat_settings"

class ContextDB(UserScopedModelDB):
    instructions = fields.TextField()
    resources = fields.JSONField()
    mcps = fields.JSONField()

    class Meta:
        table = "ccat_contexts"

class ChatDB(UserScopedModelDB):
    messages = fields.JSONField()
    context = fields.ForeignKeyField(
        'models.ContextDB', related_name='chats', db_index=True
    )
    
    class Meta:
        table = "ccat_chats"



# necessary for relationships
Tortoise.init_models(["cat.db.models"], "models")