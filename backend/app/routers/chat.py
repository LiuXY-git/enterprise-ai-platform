from fastapi import APIRouter

from ..models.chat import ChatRequest, ChatResponse
from ..services.chat_service import build_reply

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    reply = build_reply(request.message)
    return ChatResponse(reply=reply)
