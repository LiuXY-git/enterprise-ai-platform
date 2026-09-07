from dataclasses import dataclass
from typing import Any

import httpx

from .feishu_config import get_feishu_config


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
