from fastapi import FastAPI

from .routers.chat import router as chat_router
from .routers.health import router as health_router

app = FastAPI(
    title="Enterprise AI Platform",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(chat_router)
