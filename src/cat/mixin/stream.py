from typing import Callable, Dict
from cat.protocols.agui import events


class EventStreamMixin:
    """Mixin for sending messages and events to clients."""

    async def send_json(self, data: Dict):
        """Send JSON data to the client."""
        if self.stream_callback:
            await self.stream_callback(data)
        
    async def agui_event(self, event: events.BaseEvent):
        """Send an AGUI event to the client."""
        await self.send_json(dict(event))
