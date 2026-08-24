from fastapi import APIRouter

from ..models.chat import ChatRequest, ChatResponse
from ..services.chat_service import build_reply

router = APIRouter(tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="发送聊天消息",
    description=(
        "接收一条聊天消息并返回平台回复。该接口用于验证基础聊天请求和响应流程。"
    ),
    response_description="平台生成的聊天回复。",
    responses={
        422: {
            "description": "请求参数校验失败。",
        },
    },
)
async def chat(request: ChatRequest) -> ChatResponse:
    reply = build_reply(request.message)
    return ChatResponse(reply=reply)
