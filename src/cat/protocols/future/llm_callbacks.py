from uuid import uuid4
import time
from langchain_core.callbacks.base import BaseCallbackHandler
from cat.protocols.agui import events


class NewTokenHandler(BaseCallbackHandler):

    def __init__(self, callback):
        self.callback = callback

    async def on_chat_model_start(self, *args, **kwargs):
        """Emit AGUI event for text streaming start."""
        await self.callback(
            events.TextMessageStartEvent(
                message_id=str(uuid4()),
                timestamp=int(time.time())
            )
        )

    async def on_llm_new_token(self, token: str, *args, **kwargs) -> None:
        """Emit AGUI event for each token."""
        if len(token) > 0:
            await self.callback(
                events.TextMessageContentEvent(
                    message_id=str(uuid4()),
                    delta=token,
                    timestamp=int(time.time())
                )
            )
            
    async def on_llm_end(self, *args, **kwargs):
        """Emit AGUI event for text streaming end."""
        await self.callback(
            events.TextMessageEndEvent(
                message_id=str(uuid4()),
                timestamp=int(time.time())
            )
        )