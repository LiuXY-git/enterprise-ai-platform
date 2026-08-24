from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = Field(
        description="服务运行状态。",
        examples=["ok"],
    )
