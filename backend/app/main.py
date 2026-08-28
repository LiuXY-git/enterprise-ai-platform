import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import init_database
from .logging_config import LOGGER_NAME, configure_logging
from .routers.chat import router as chat_router
from .routers.dify import router as dify_router
from .routers.external_knowledge import router as external_knowledge_router
from .routers.health import router as health_router
from .routers.rag import router as rag_router
from .routers.upload import router as upload_router

logger = logging.getLogger(LOGGER_NAME)

API_DESCRIPTION = """
Enterprise AI Platform 是一个面向企业知识库场景的 AI 平台。

## 核心能力

- 上传并解析 PDF、DOCX 和 Markdown 文档
- 自动切分文档并建立向量索引
- 跨多个文档检索相关内容
- 使用 RAG 生成带来源引用的回答
- 支持 DeepSeek 和通义千问模型切换

## 接口说明

- `/health`：检查服务运行状态
- `/chat`：基础聊天接口
- `/dify/workflow`：由 FastAPI 调用 Dify 企业咨询工作流
- `/upload`：上传、解析并索引文档
- `/rag/query`：检索相关文档片段
- `/rag/answer`：生成带来源引用的回答
- `/retrieval`：为 Dify 提供外部知识库检索
"""

OPENAPI_TAGS = [
    {
        "name": "system",
        "description": "服务状态与运行检查接口。",
    },
    {
        "name": "chat",
        "description": "基础聊天功能接口。",
    },
    {
        "name": "dify",
        "description": "FastAPI 调用 Dify 应用工作流的集成接口。",
    },
    {
        "name": "documents",
        "description": "文档上传、解析和自动索引接口。",
    },
    {
        "name": "knowledge",
        "description": "Dify 外部知识库检索与集成接口。",
    },
    {
        "name": "rag",
        "description": "知识库检索和带来源回答接口。",
    },
]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()

    logger.info("正在启动 Enterprise AI Platform")

    try:
        init_database()
    except Exception:
        logger.exception("数据库初始化失败")
        raise

    logger.info("数据库初始化成功")

    try:
        yield
    finally:
        logger.info("Enterprise AI Platform 已停止")


app = FastAPI(
    title="Enterprise AI Platform",
    summary="企业知识库与 RAG API",
    description=API_DESCRIPTION,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(dify_router)
app.include_router(upload_router)
app.include_router(external_knowledge_router)
app.include_router(rag_router)
