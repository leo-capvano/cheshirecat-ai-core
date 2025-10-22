import os
import json
from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, FileResponse

from cat.types import ChatRequest, ChatResponse
from cat.auth.permissions import AuthResource, AuthPermission, check_permissions
from cat.utils import get_base_path

router = APIRouter(prefix="", tags=["Home"])


@router.get("/", include_in_schema=False)
async def frontend(
)-> FileResponse:
    
    ui_index = os.path.join(get_base_path(), "routes/static/core_static_folder/ui/index.html")
    return FileResponse(ui_index)

        
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
