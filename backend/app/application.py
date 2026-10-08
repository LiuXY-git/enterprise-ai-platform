"""Build independent FastAPI applications without starting external resources."""

from copy import deepcopy

from fastapi import FastAPI

from .core.lifecycle import lifespan
from .core.metadata import API_DESCRIPTION, OPENAPI_TAGS
from .core.request_logging import LoggedFastAPI
from .routers.registry import register_routes


def create_app() -> FastAPI:
    """Construct routes and metadata; database and logging start in lifespan."""
    application = LoggedFastAPI(
        title="Enterprise AI Platform",
        summary="企业知识库、RAG 与工作流自动化 API",
        description=API_DESCRIPTION,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=deepcopy(OPENAPI_TAGS),
        lifespan=lifespan,
    )
    register_routes(application)
    return application
