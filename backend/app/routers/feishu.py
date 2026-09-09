from fastapi import APIRouter, HTTPException, status

from ..models.feishu import FeishuMessageResponse, FeishuTextMessageRequest
from ..services.feishu_service import send_feishu_text_message

router = APIRouter(
    prefix="/integrations/feishu",
    tags=["integrations"],
)


@router.post(
    "/messages",
    response_model=FeishuMessageResponse,
    summary="通过飞书机器人发送文本消息",
    description=(
        "向服务端配置的测试成员或测试群发送文本消息。"
        "接收者和飞书凭证由服务端读取；调用方仅提交正文和幂等键。"
        "成功表示飞书接口已确认发送，不代表接收者已读。"
    ),
    responses={
        422: {"description": "正文、幂等键或请求字段不符合要求。"},
        503: {"description": "飞书配置、鉴权或消息发送失败。"},
    },
)
async def send_message(
    request: FeishuTextMessageRequest,
) -> FeishuMessageResponse:
    try:
        result = await send_feishu_text_message(
            request.text,
            idempotency_key=request.idempotency_key,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return FeishuMessageResponse(
        status="sent",
        message_id=result.message_id,
        attempts=result.attempts,
    )
