from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=2000,
        description="用户发送的聊天消息。",
        examples=["你好，请介绍一下这个平台。"],
    )


class ChatResponse(BaseModel):
    reply: str = Field(
        description="平台生成的回复内容。",
        examples=["你好，这是 Enterprise AI Platform。"],
    )
