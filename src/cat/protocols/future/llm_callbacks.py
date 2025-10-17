from uuid import UUID, uuid4
import time
from langchain_core.callbacks.base import BaseCallbackHandler
from cat.protocols.agui import events
from cat.env import get_env
from cat.log import log


class NewTokenHandler(BaseCallbackHandler):

    def __init__(self, cat):
        self.cat = cat

    async def on_chat_model_start(self, *args, **kwargs):
        """Emit AGUI event for text streaming start."""
        await self.cat.agui_event(
            events.TextMessageStartEvent(
                message_id=str(uuid4()),
                timestamp=int(time.time())
            )
        )

    async def on_llm_new_token(self, token: str, *args, **kwargs) -> None:
        """Emit AGUI event for each token."""
        if len(token) > 0:
            await self.cat.agui_event(
                events.TextMessageContentEvent(
                    message_id=str(uuid4()),
                    delta=token,
                    timestamp=int(time.time())
                )
            )
            
    async def on_llm_end(self, *args, **kwargs):
        """Emit AGUI event for text streaming end."""
        await self.cat.agui_event(
            events.TextMessageEndEvent(
                message_id=str(uuid4()),
                timestamp=int(time.time())
            )
        )