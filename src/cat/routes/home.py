import json
from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse

from cat.types import ChatRequest, ChatResponse
from cat.auth import AuthResource, AuthPermission, check_permissions

router = APIRouter(prefix="", tags=["Home"])

      
@router.post("/message")
async def message(
    chat_request: ChatRequest = Body(
        ..., 
        example={
            "agent": "default",
            "model": "openai:gpt-4o",
            "system_prompt": "You are the Cheshire Cat, and always talk in rhymes.",
            "messages": [
                {
                    "role": "user",
                    "content": {"type": "text", "text": "Meow!"}
                }
            ],
            "stream": False,
        }
    ),
    cat=check_permissions(AuthResource.CHAT, AuthPermission.EDIT),
) -> ChatResponse:
    
    if chat_request.stream:
        async def event_stream():
            async for msg in cat.run(chat_request):
                yield f"data: {json.dumps(dict(msg))}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    else:
        return await cat(chat_request)
