import httpx
from fastapi import APIRouter, HTTPException, Request, status

from ..models.wecom import WeComMessageResponse, WeComTextMessageRequest
from ..services.wecom_config import get_wecom_config
from ..services.wecom_service import WeComDeliveryUnknownError, WeComMessageService

router = APIRouter(prefix="/integrations/wecom", tags=["integrations"])


def _get_message_service(request: Request) -> WeComMessageService:
    # 按需校验：未配置企业微信不会阻止应用启动或其他接口使用。
    config = get_wecom_config()
    cached = getattr(request.app.state, "wecom_cache", None)

    # 本函数在异步路由内同步执行，检查与赋值之间没有 await。
    # 配置变化后换实例，避免新凭据复用旧 Token。
    if cached is None or cached[0] != config:
        cached = (config, WeComMessageService(config))
        request.app.state.wecom_cache = cached

    return cached[1]


def _create_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient()


@router.post(
    "/messages",
    response_model=WeComMessageResponse,
    summary="通过企业微信自建应用发送文本消息",
    description=(
        "向服务端配置的一个测试成员发送文本消息。"
        "调用方仅提交正文与 request_id；request_id 用于追踪，不保证去重。"
        "成功表示上游接口确认发送，不代表成员已读。"
        "若返回 delivery_unknown，请先核对实际接收情况，不要自动重发。"
    ),
    responses={
        422: {"description": "正文、请求标识或请求字段不符合要求。"},
        503: {
            "description": (
                "配置、鉴权或发送异常。detail.code 为 wecom_unavailable 或 "
                "delivery_unknown；后者表示发送结果不确定，不应自动重试。"
            ),
        },
    },
)
async def send_message(
    payload: WeComTextMessageRequest,
    request: Request,
) -> WeComMessageResponse:
    try:
        service = _get_message_service(request)
        async with _create_http_client() as client:
            return await service.send_text_message(payload, client=client)
    except WeComDeliveryUnknownError:
        # 子类必须先捕获，否则会被下面的 RuntimeError 捕获。
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "delivery_unknown",
                "message": "企业微信发送结果不确定，请核对实际接收情况，不要自动重发。",
                "request_id": payload.request_id,
            },
        ) from None
    except RuntimeError as exc:
        # 此处接收配置与服务层已经清理过的 RuntimeError，不透传原始 HTTP 异常。
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "wecom_unavailable",
                "message": str(exc),
                "request_id": payload.request_id,
            },
        ) from None
