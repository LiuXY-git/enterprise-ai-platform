"""Register the public HTTP routers in their existing OpenAPI order."""

from fastapi import FastAPI

from .chat import router as chat_router
from .crm import router as crm_router
from .dify import router as dify_router
from .external_knowledge import router as external_knowledge_router
from .feishu import router as feishu_router
from .health import router as health_router
from .rag import router as rag_router
from .upload import router as upload_router
from .wecom import router as wecom_router
from .workflow import router as workflow_router

ROUTERS = (
    health_router,
    chat_router,
    dify_router,
    upload_router,
    external_knowledge_router,
    rag_router,
    workflow_router,
    crm_router,
    feishu_router,
    wecom_router,
)


def register_routes(app: FastAPI) -> None:
    for router in ROUTERS:
        app.include_router(router)
