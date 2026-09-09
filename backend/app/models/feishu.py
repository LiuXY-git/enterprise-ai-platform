from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FeishuTextMessageRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    text: str = Field(
        min_length=1,
        max_length=4000,
        description="需要通过飞书机器人发送的文本。",
        examples=["Day 44 飞书机器人测试消息"],
    )
    idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
        description=(
            "标识一次逻辑发送。同一消息重试时复用此值；发送新消息时使用新值。"
        ),
        examples=["day44-smoke-001"],
    )


class FeishuMessageResponse(BaseModel):
    status: Literal["sent"] = Field(
        description="飞书消息接口已确认发送成功，不代表接收者已读。",
    )
    message_id: str = Field(
        min_length=1,
        description="飞书返回的消息 ID。",
        examples=["om_example"],
    )
    attempts: int = Field(
        ge=1,
        le=5,
        description="消息发送请求的实际尝试次数，包含首次请求。",
    )
