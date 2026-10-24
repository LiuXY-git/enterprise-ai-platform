"""Fixed server-side template registry and strict browser input contracts."""

from datetime import date
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class CustomerInput(Input):
    customer_id: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=2000)
    priority: Literal["normal", "high"] = "normal"


class EmailInput(Input):
    requester: str = Field(min_length=1, max_length=80)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)
    priority: Literal["normal", "high"] = "normal"


class LeadInput(Input):
    customer_id: str = Field(min_length=1, max_length=80)
    company_name: str = Field(min_length=1, max_length=160)
    industry: str = Field(min_length=1, max_length=100)
    requirement: str = Field(min_length=1, max_length=2000)
    purchase_window_days: int = Field(ge=1, le=3650)
    sales_owner: str = Field(min_length=1, max_length=80)
    report_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")

    @model_validator(mode="after")
    def valid_date(self):
        date.fromisoformat(self.report_date)
        return self


TEMPLATES = {
    "customer-service": {
        "name": "企业客服咨询",
        "path": "console-customer-service",
        "model": CustomerInput,
        "dependencies": "n8n + Dify",
        "example": {
            "customer_id": "demo-customer",
            "message": "知识库支持哪些文档格式？",
            "priority": "normal",
        },
    },
    "email-assistant": {
        "name": "邮件分类与回复草稿",
        "path": "console-email-assistant",
        "model": EmailInput,
        "dependencies": "n8n + Dify + 平台 API",
        "example": {
            "requester": "demo-user",
            "subject": "文档格式咨询",
            "body": "请说明知识库支持的文档格式。",
            "priority": "normal",
        },
    },
    "sales-followup": {
        "name": "销售线索与 CRM 跟进",
        "path": "console-sales-followup",
        "model": LeadInput,
        "dependencies": "n8n + Qwen + 平台 API",
        "example": {
            "customer_id": "demo-company",
            "company_name": "示例企业（虚构）",
            "industry": "制造业",
            "requirement": "希望整理内部资料供员工检索。",
            "purchase_window_days": 60,
            "sales_owner": "demo-sales",
            "report_date": "2026-10-24",
        },
    },
}


class WorkflowRequest(Input):
    template_id: Literal["customer-service", "email-assistant", "sales-followup"]
    mode: Literal["fixture", "live"] = "fixture"
    input: dict
    confirm_live: bool = False

    @model_validator(mode="after")
    def validate_template(self):
        self.input = (
            TEMPLATES[self.template_id]["model"].model_validate(self.input).model_dump()
        )
        if self.mode == "live" and not self.confirm_live:
            raise ValueError("live_confirmation_required")
        return self


def configured_url(base):
    if not base:
        return None
    parts = urlsplit(base)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or parts.path not in {"", "/"}
    ):
        return None
    return base.rstrip("/")


def catalog(base):
    return [
        {
            "id": key,
            "name": value["name"],
            "example": value["example"],
            "schema": value["model"].model_json_schema(),
            "dependencies": value["dependencies"],
            "live_configured": bool(configured_url(base)),
            "live_verified": False,
            "notice": "配置存在不代表已导入、激活或连接验证通过；邮件仅草稿，销售通知仅预览。",
        }
        for key, value in TEMPLATES.items()
    ]
