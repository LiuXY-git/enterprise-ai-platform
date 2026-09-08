import json
import logging
from asyncio import sleep
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import httpx

from ..logging_config import LOGGER_NAME
from .feishu_config import get_feishu_config
from .feishu_message_config import (
    FeishuMessageConfig,
    get_feishu_message_config,
)

logger = logging.getLogger(LOGGER_NAME)


@dataclass(frozen=True)
class FeishuTenantToken:
    access_token: str
    expires_in: int


def _parse_token_response(
    response_body: dict[str, Any],
) -> FeishuTenantToken:
    code = response_body.get("code")

    if code != 0:
        raise RuntimeError(
            f"飞书鉴权失败（业务错误码 {code}）",
        )

    access_token = response_body.get(
        "tenant_access_token",
    )
    expires_in = response_body.get("expire")

    if not isinstance(access_token, str) or not access_token.strip():
        raise RuntimeError(
            "飞书鉴权响应缺少 tenant_access_token",
        )

    if not isinstance(expires_in, int) or expires_in <= 0:
        raise RuntimeError(
            "飞书鉴权响应缺少有效期",
        )

    return FeishuTenantToken(
        access_token=access_token,
        expires_in=expires_in,
    )


async def get_feishu_tenant_token() -> FeishuTenantToken:
    config = get_feishu_config()
    endpoint = f"{config.base_url}/auth/v3/tenant_access_token/internal"
    payload = {
        "app_id": config.app_id,
        "app_secret": config.app_secret,
    }

    try:
        async with httpx.AsyncClient(
            timeout=config.timeout_seconds,
        ) as client:
            response = await client.post(
                endpoint,
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"飞书鉴权失败（HTTP {exc.response.status_code}）",
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(
            "无法连接飞书开放平台",
        ) from exc

    try:
        response_body = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "飞书鉴权接口返回了无效 JSON",
        ) from exc

    if not isinstance(response_body, dict):
        raise RuntimeError(
            "飞书鉴权接口返回格式错误",
        )

    return _parse_token_response(response_body)


@dataclass(frozen=True)
class FeishuMessageResult:
    message_id: str
    attempts: int


def _parse_message_response(
    response_body: object,
) -> str:
    if not isinstance(response_body, dict):
        raise RuntimeError("飞书消息接口返回格式错误")

    code = response_body.get("code")

    # 必须是整数，避免把 False 误判为数字 0。
    if type(code) is not int:
        raise RuntimeError("飞书消息响应缺少有效业务错误码")

    if code != 0:
        raise RuntimeError(
            f"飞书消息发送失败（业务错误码 {code}）",
        )

    data = response_body.get("data")

    if not isinstance(data, dict):
        raise RuntimeError("飞书消息响应缺少 data")

    message_id = data.get("message_id")

    if not isinstance(message_id, str) or not message_id.strip():
        raise RuntimeError("飞书消息响应缺少 message_id")

    return message_id.strip()


async def _post_message_with_retry(
    client: httpx.AsyncClient,
    *,
    endpoint: str,
    params: dict[str, str],
    headers: dict[str, str],
    payload: dict[str, str],
    message_config: FeishuMessageConfig,
) -> tuple[httpx.Response, int]:
    for attempt in range(1, message_config.max_attempts + 1):
        retry_after = None

        try:
            response = await client.post(
                endpoint,
                params=params,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            error = f"飞书消息发送失败（HTTP {status_code}）"

            try:
                error_body = exc.response.json()
            except ValueError:
                error_body = {}

            business_code = (
                error_body.get("code") if isinstance(error_body, dict) else None
            )

            if type(business_code) is int:
                error += f"（业务错误码 {business_code}）"

            retryable = status_code in {429, 500, 502, 503, 504}
            retry_after = exc.response.headers.get("Retry-After")
        except httpx.RequestError:
            error = "无法连接飞书消息服务"
            retryable = True
        else:
            return response, attempt

        logger.warning(
            "飞书消息请求失败 attempt=%s/%s reason=%s",
            attempt,
            message_config.max_attempts,
            error,
        )

        if not retryable or attempt == message_config.max_attempts:
            raise RuntimeError(error)

        delay = message_config.retry_base_seconds * 2 ** (attempt - 1)

        if retry_after is not None:
            try:
                server_delay = int(retry_after)
                if server_delay < 0:
                    raise ValueError
            except ValueError:
                raise RuntimeError(
                    "飞书返回了无法处理的 Retry-After，请稍后重试",
                ) from None

            delay = max(delay, server_delay)

        if delay > 30:
            raise RuntimeError("飞书重试等待超过 30 秒，请稍后重试")

        logger.info("飞书消息准备重试 wait_seconds=%s", delay)
        await sleep(delay)

    raise RuntimeError("飞书消息发送尝试次数配置无效")


async def send_feishu_text_message(
    text: str,
    *,
    idempotency_key: str,
) -> FeishuMessageResult:
    config = get_feishu_config()
    message_config = get_feishu_message_config()

    # 复用 Day 43 的鉴权服务。
    token = await get_feishu_tenant_token()

    # 同一应用、接收者和幂等键生成相同的 UUID。
    uuid_source = json.dumps(
        [
            config.app_id,
            message_config.receive_id_type,
            message_config.receive_id,
            idempotency_key,
        ],
        ensure_ascii=False,
    )
    message_uuid = str(uuid5(NAMESPACE_URL, uuid_source))

    endpoint = f"{config.base_url}/im/v1/messages"

    params = {
        "receive_id_type": message_config.receive_id_type,
    }
    headers = {
        "Authorization": f"Bearer {token.access_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {
        "receive_id": message_config.receive_id,
        "msg_type": "text",
        "content": json.dumps(
            {"text": text},
            ensure_ascii=False,
        ),
        "uuid": message_uuid,
    }

    async with httpx.AsyncClient(
        timeout=config.timeout_seconds,
    ) as client:
        response, attempts = await _post_message_with_retry(
            client,
            endpoint=endpoint,
            params=params,
            headers=headers,
            payload=payload,
            message_config=message_config,
        )

    try:
        response_body = response.json()
    except ValueError as exc:
        logger.warning("飞书消息接口返回了无效 JSON")
        raise RuntimeError(
            "飞书消息接口返回了无效 JSON",
        ) from exc

    try:
        message_id = _parse_message_response(response_body)
    except RuntimeError as exc:
        logger.warning("飞书消息响应校验失败 reason=%s", str(exc))
        raise

    logger.info("飞书消息发送成功 attempts=%s", attempts)

    return FeishuMessageResult(
        message_id=message_id,
        attempts=attempts,
    )
