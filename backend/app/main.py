"""Stable ASGI entry point used by Uvicorn and the existing Docker command."""

from .application import create_app

app = create_app()
