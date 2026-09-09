import asyncio
import logging
import time
from collections.abc import Callable

import httpx

from backend.app.services.wecom_config import WeComConfig


class _HideWeComRequestLog(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # HTTPX 的请求日志可能包含带 Secret 或 Token 的 URL。
        return "qyapi.weixin.qq.com" not in record.getMessage().lower()


logging.getLogger("httpx").addFilter(_HideWeComRequestLog())


class WeComTokenProvider:
    def __init__(
        self,
        config: WeComConfig,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._clock = clock
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def get_token(self, client: httpx.AsyncClient) -> str:
        async with self._lock:
            # 必须在锁内检查，避免并发请求重复刷新。
            if self._token is not None and self._clock() < self._expires_at:
                return self._token

            requested_at = self._clock()
            token, expires_in = await self._fetch_token(client)

            # 项目策略：提前过期，最多提前 60 秒。
            margin = min(60.0, expires_in * 0.1)

            self._token = token
            self._expires_at = requested_at + expires_in - margin

            return token

    async def invalidate(self, rejected_token: str) -> None:
        async with self._lock:
            # 旧请求报告失效时，不要误删已经更新的新 Token。
            if self._token == rejected_token:
                self._token = None
                self._expires_at = 0.0

    async def _fetch_token(
        self,
        client: httpx.AsyncClient,
    ) -> tuple[str, int]:
        try:
            response = await client.get(
                f"{self._config.base_url}/cgi-bin/gettoken",
                params={
                    "corpid": self._config.corp_id,
                    "corpsecret": self._config.app_secret,
                },
                timeout=self._config.timeout_seconds,
                follow_redirects=False,
            )
        except httpx.RequestError:
            # 不附带原始异常：其中可能包含带密钥的 URL。
            raise RuntimeError("企业微信 Token 请求网络异常") from None

        if response.status_code != 200:
            raise RuntimeError(
                f"企业微信 Token 请求失败（HTTP {response.status_code}）"
            )

        try:
            body = response.json()
        except ValueError:
            raise RuntimeError("企业微信 Token 响应不是合法 JSON") from None

        if not isinstance(body, dict):
            raise RuntimeError("企业微信 Token 响应格式错误")

        # 兼容成功响应未携带 errcode 的形式；
        # 如果字段存在，就必须是整数 0。
        if "errcode" in body:
            error_code = body["errcode"]

            # bool 是 int 的子类，不能用 isinstance(..., int) 判断。
            if type(error_code) is not int:
                raise RuntimeError("企业微信 Token 错误码格式错误")

            if error_code != 0:
                # 只保留数值错误码，不直接透传上游 errmsg。
                raise RuntimeError(
                    f"企业微信 Token 获取失败（业务错误码 {error_code}）"
                )

        token = body.get("access_token")
        expires_in = body.get("expires_in")

        if not isinstance(token, str) or not token.strip():
            raise RuntimeError("企业微信 Token 响应缺少有效 access_token")

        if type(expires_in) is not int or expires_in <= 0:
            raise RuntimeError("企业微信 Token 响应缺少有效 expires_in")

        return token.strip(), expires_in
