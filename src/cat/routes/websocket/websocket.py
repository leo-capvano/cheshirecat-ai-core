
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from cat.auth import AuthPermission, AuthResource
from cat.auth.connection import WebsocketConnection
from cat import log

router = APIRouter(tags=["Websocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    cat=Depends(WebsocketConnection(AuthResource.CHAT, AuthPermission.EDIT))
):
    await websocket.accept()

    try:
        while True:

            # Receive the next message from WebSocket.
            user_message = await websocket.receive_json()

            async for msg in cat.stream(user_message):
                await websocket.send_json(msg)

    except WebSocketDisconnect:
        log.info(f"WebSocket connection closed for user {cat.user_id}")
    except Exception:
        log.error("Error in websocket loop")