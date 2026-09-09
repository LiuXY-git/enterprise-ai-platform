import httpx

from backend.app.models.wecom import WeComMessageResponse, WeComTextMessageRequest
from backend.app.services.wecom_config import WeComConfig
from backend.app.services.wecom_token_service import WeComTokenProvider

TOKEN_INVALID_CODES = {40014, 42001}


class WeComDeliveryUnknownError(RuntimeError):
    """The request may have reached WeCom; do not automatically resend it."""


class WeComMessageService:
    def __init__(self, config: WeComConfig) -> None:
        self._config = config
        # Reuse this service instance to reuse its token cache.
        self._tokens = WeComTokenProvider(config)

    async def send_text_message(
        self,
        request: WeComTextMessageRequest,
        *,
        client: httpx.AsyncClient,
    ) -> WeComMessageResponse:
        payload = {
            "touser": self._config.to_user,
            "msgtype": "text",
            "agentid": self._config.agent_id,
            "text": {"content": request.text},
            "safe": 0,
        }

        for attempt in range(1, 3):
            token = await self._tokens.get_token(client)

            try:
                response = await client.post(
                    f"{self._config.base_url}/cgi-bin/message/send",
                    params={"access_token": token},
                    json=payload,
                    timeout=self._config.timeout_seconds,
                    follow_redirects=False,
                )
            except httpx.RequestError:
                # Never include the original exception or its sensitive URL.
                raise WeComDeliveryUnknownError(
                    "delivery_unknown: 企业微信发送网络异常，结果不确定，请勿自动重发"
                ) from None

            if response.status_code == 408 or response.status_code >= 500:
                raise WeComDeliveryUnknownError(
                    "delivery_unknown: 企业微信发送结果不确定"
                    f"（HTTP {response.status_code}），请勿自动重发"
                )

            if response.status_code != 200:
                raise RuntimeError(
                    f"企业微信消息请求未成功（HTTP {response.status_code}）"
                )

            body = self._parse_body(response)
            error_code = body["errcode"]

            if error_code in TOKEN_INVALID_CODES:
                await self._tokens.invalidate(token)
                if attempt == 1:
                    continue

            if error_code != 0:
                raise RuntimeError(f"企业微信消息发送失败（业务错误码 {error_code}）")

            return self._build_result(body, request, attempt)

        raise RuntimeError("企业微信消息发送未完成")

    @staticmethod
    def _parse_body(response: httpx.Response) -> dict:
        try:
            body = response.json()
        except ValueError:
            raise WeComDeliveryUnknownError(
                "delivery_unknown: 企业微信响应不是合法 JSON，请勿自动重发"
            ) from None

        if not isinstance(body, dict) or type(body.get("errcode")) is not int:
            raise WeComDeliveryUnknownError(
                "delivery_unknown: 企业微信响应格式异常，请勿自动重发"
            )

        return body

    @staticmethod
    def _build_result(
        body: dict,
        request: WeComTextMessageRequest,
        attempt: int,
    ) -> WeComMessageResponse:
        # Even errcode=0 must not conceal rejected recipients.
        for field in ("invaliduser", "invalidparty", "invalidtag", "unlicenseduser"):
            rejected = body.get(field, "")
            if not isinstance(rejected, str):
                raise WeComDeliveryUnknownError(
                    "delivery_unknown: 企业微信接收者结果格式异常，请勿自动重发"
                )
            if rejected.strip():
                raise RuntimeError("企业微信响应包含未成功接收的对象，请核对成员配置")

        message_id = body.get("msgid")
        if message_id is not None:
            if not isinstance(message_id, str) or not message_id.strip():
                raise WeComDeliveryUnknownError(
                    "delivery_unknown: 企业微信消息 ID 格式异常，请勿自动重发"
                )
            message_id = message_id.strip()

        return WeComMessageResponse(
            status="sent",
            message_id=message_id,
            request_id=request.request_id,
            attempts=attempt,
        )
