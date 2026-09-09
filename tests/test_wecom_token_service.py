import asyncio

import httpx
import pytest

from backend.app.services.wecom_config import WeComConfig
from backend.app.services.wecom_token_service import WeComTokenProvider


def build_config():
    return WeComConfig(
        corp_id="ww_test_corp",
        agent_id=1000002,
        app_secret="fake-secret",
        to_user="test_member",
        base_url="https://qyapi.weixin.qq.com",
        timeout_seconds=10,
    )


def test_fetch_token_and_reuse_cache():
    async def scenario():
        captured = []

        def handler(request):
            captured.append(request)

            return httpx.Response(
                200,
                json={
                    "errcode": 0,
                    "access_token": "fake-token",
                    "expires_in": 7200,
                },
            )

        provider = WeComTokenProvider(build_config())

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            first = await provider.get_token(client)
            second = await provider.get_token(client)

        assert first == second == "fake-token"
        assert len(captured) == 1

        request = captured[0]
        assert request.method == "GET"
        assert request.url.path == "/cgi-bin/gettoken"
        assert request.url.params["corpid"] == "ww_test_corp"
        assert request.url.params["corpsecret"] == "fake-secret"
        assert request.extensions["timeout"]["read"] == 10

    asyncio.run(scenario())


def test_refreshes_at_safety_margin():
    async def scenario():
        now = [100.0]
        calls = []

        def handler(request):
            calls.append(request)

            return httpx.Response(
                200,
                json={
                    "access_token": f"fake-token-{len(calls)}",
                    "expires_in": 100,
                },
            )

        provider = WeComTokenProvider(
            build_config(),
            clock=lambda: now[0],
        )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            assert await provider.get_token(client) == "fake-token-1"

            # 100 秒有效期，项目策略提前 10 秒刷新。
            now[0] = 189.0
            assert await provider.get_token(client) == "fake-token-1"

            now[0] = 190.0
            assert await provider.get_token(client) == "fake-token-2"

        assert len(calls) == 2

    asyncio.run(scenario())


def test_concurrent_requests_share_one_fetch():
    async def scenario():
        calls = []

        async def handler(request):
            calls.append(request)
            await asyncio.sleep(0)

            return httpx.Response(
                200,
                json={
                    "access_token": "shared-token",
                    "expires_in": 7200,
                },
            )

        provider = WeComTokenProvider(build_config())

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            results = await asyncio.gather(
                *(provider.get_token(client) for _ in range(5))
            )

        assert results == ["shared-token"] * 5
        assert len(calls) == 1

    asyncio.run(scenario())


def test_invalidate_does_not_remove_new_token():
    async def scenario():
        calls = []

        def handler(request):
            calls.append(request)

            return httpx.Response(
                200,
                json={
                    "access_token": f"fake-token-{len(calls)}",
                    "expires_in": 7200,
                },
            )

        provider = WeComTokenProvider(build_config())

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            old_token = await provider.get_token(client)
            await provider.invalidate(old_token)

            new_token = await provider.get_token(client)
            assert new_token == "fake-token-2"

            # 迟到的旧请求，不应清除新缓存。
            await provider.invalidate(old_token)
            assert await provider.get_token(client) == new_token

        assert len(calls) == 2

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "body",
    [
        [],
        {},
        {"errcode": 40013, "errmsg": "sensitive-upstream-detail"},
        {"errcode": "0"},
        {"errcode": False},
        {"access_token": "", "expires_in": 7200},
        {"access_token": "   ", "expires_in": 7200},
        {"access_token": 123, "expires_in": 7200},
        {"access_token": "token", "expires_in": 0},
        {"access_token": "token", "expires_in": -1},
        {"access_token": "token", "expires_in": True},
        {"access_token": "token", "expires_in": "7200"},
    ],
)
def test_rejects_invalid_body_without_caching(body):
    async def scenario():
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(200, json=body)

        provider = WeComTokenProvider(build_config())

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            for _ in range(2):
                with pytest.raises(RuntimeError) as caught:
                    await provider.get_token(client)

                assert "fake-secret" not in str(caught.value)
                assert "sensitive-upstream-detail" not in str(caught.value)

        # 失败响应没有进入缓存。
        assert len(calls) == 2

    asyncio.run(scenario())


@pytest.mark.parametrize("status_code", [302, 400, 500])
def test_rejects_non_200_response(status_code):
    async def scenario():
        def handler(request):
            return httpx.Response(
                status_code,
                headers={"Location": "https://example.com"},
                text="sensitive-upstream-detail",
            )

        provider = WeComTokenProvider(build_config())

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            follow_redirects=True,
        ) as client:
            with pytest.raises(
                RuntimeError,
                match=f"HTTP {status_code}",
            ):
                await provider.get_token(client)

    asyncio.run(scenario())


def test_rejects_invalid_json():
    async def scenario():
        def handler(request):
            return httpx.Response(200, text="not-json")

        provider = WeComTokenProvider(build_config())

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            with pytest.raises(RuntimeError, match="不是合法 JSON"):
                await provider.get_token(client)

    asyncio.run(scenario())


def test_network_error_hides_original_details():
    async def scenario():
        def handler(request):
            raise httpx.ConnectError(
                "sensitive-upstream-detail fake-secret",
                request=request,
            )

        provider = WeComTokenProvider(build_config())

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            with pytest.raises(RuntimeError) as caught:
                await provider.get_token(client)

        assert str(caught.value) == "企业微信 Token 请求网络异常"
        assert caught.value.__suppress_context__ is True

    asyncio.run(scenario())


def test_httpx_log_does_not_expose_secret(caplog):
    async def scenario():
        def handler(request):
            return httpx.Response(
                200,
                json={
                    "access_token": "fake-token",
                    "expires_in": 7200,
                },
            )

        provider = WeComTokenProvider(build_config())

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            await provider.get_token(client)

    with caplog.at_level("INFO", logger="httpx"):
        asyncio.run(scenario())

    assert "fake-secret" not in caplog.text
    assert "corpsecret=" not in caplog.text
