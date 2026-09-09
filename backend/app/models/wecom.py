from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_TEXT_BYTES = 2048
REQUEST_ID_PATTERN = r"^[A-Za-z0-9._:-]+$"


class WeComTextMessageRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        strict=True,
    )

    text: str = Field(
        min_length=1,
        max_length=MAX_TEXT_BYTES,
        description="通知正文，去除首尾空白后 UTF-8 编码最多 2048 字节。",
        examples=["Day 45 企业微信测试消息"],
    )
    request_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=REQUEST_ID_PATTERN,
        description="请求追踪标识，不保证相同标识的请求不会重复发送。",
        examples=["day45-smoke-001"],
    )

    @field_validator("text")
    @classmethod
    def validate_text_bytes(cls, value: str) -> str:
        try:
            encoded = value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("text 必须能够编码为 UTF-8") from exc

        if len(encoded) > MAX_TEXT_BYTES:
            raise ValueError(f"text 的 UTF-8 长度不能超过 {MAX_TEXT_BYTES} 字节")

        return value


class WeComMessageResponse(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        strict=True,
    )

    status: Literal["sent"] = Field(
        description="上游接口确认发送成功，不代表成员已读。",
    )
    message_id: str | None = Field(
        default=None,
        min_length=1,
        description="上游返回的消息 ID，未返回时为 null。",
    )
    request_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=REQUEST_ID_PATTERN,
        description="对应请求的追踪标识。",
    )
    attempts: int = Field(
        ge=1,
        le=2,
        description="实际消息发送请求次数，不包含获取 Token 的请求。",
    )
