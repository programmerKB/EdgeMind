"""Assemble all feature routers from explicitly injected dependencies."""

from fastapi import APIRouter

from edgemind.application.chat_history import ChatHistoryService
from edgemind.presentation.api.routes import (
    artifacts,
    chat,
    conversations,
    health,
    performance,
    predictions,
    sensors,
)


def create_api_router(container) -> APIRouter:
    """Build the versionless API tree without accessing global services."""
    router = APIRouter()
    history = ChatHistoryService()
    router.include_router(health.create_router(container.uow_factory))
    router.include_router(
        sensors.create_router(container.sensors, container.uow_factory)
    )
    router.include_router(
        predictions.create_router(container.forecasts, container.uow_factory)
    )
    router.include_router(performance.create_router(container.reports))
    router.include_router(artifacts.create_router(container.reports))
    router.include_router(conversations.create_router(history, container.uow_factory))
    router.include_router(chat.create_router(container.agent, history, container.uow_factory))
    return router
