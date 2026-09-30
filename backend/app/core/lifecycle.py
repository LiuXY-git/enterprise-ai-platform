"""Startup and shutdown side effects run only inside the ASGI lifespan."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..database import init_database
from ..logging_config import LOGGER_NAME, configure_logging
from ..settings import load_environment

logger = logging.getLogger(LOGGER_NAME)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    load_environment()
    configure_logging()
    app.state.wecom_cache = None

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
        app.state.wecom_cache = None
        logger.info("Enterprise AI Platform 已停止")
