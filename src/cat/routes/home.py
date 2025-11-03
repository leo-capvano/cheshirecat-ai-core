import os
import json
from fastapi import APIRouter, Path, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, RedirectResponse

from cat.types import ChatRequest, ChatResponse
from cat.auth.permissions import AuthResource, AuthPermission, check_permissions
from cat.utils import get_base_path

router = APIRouter(prefix="", tags=["Home"])

@router.get("/", include_in_schema=False)
async def frontend(
)-> RedirectResponse:
    # spa physically under /ui to avoid api and plugins route clashes
    return RedirectResponse(url="/ui")

        
@router.post("/message")
async def message(
    chat_request: ChatRequest,
    cat=check_permissions(AuthResource.CHAT, AuthPermission.EDIT),
) -> ChatResponse:
    
    if chat_request.stream:
        async def event_stream():
            async for msg in cat.run(chat_request):
                yield f"data: {json.dumps(dict(msg))}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    else:
        return await cat(chat_request)
