import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import init_database
from .logging_config import LOGGER_NAME, configure_logging
from .routers.chat import router as chat_router
from .routers.health import router as health_router
from .routers.rag import router as rag_router
from .routers.upload import router as upload_router

logger = logging.getLogger(LOGGER_NAME)


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
    version="0.3.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(upload_router)
app.include_router(rag_router)
