"""List, create, and reopen browser-scoped diagnostic conversations."""

from dataclasses import asdict
from typing import Callable
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status

from edgemind.application.chat_history import ChatHistoryService, ConversationNotFound
from edgemind.application.ports import UnitOfWork
from edgemind.presentation.schemas import CreateConversationRequest


def create_router(
    history: ChatHistoryService,
    uow_factory: Callable[[], UnitOfWork],
) -> APIRouter:
    router = APIRouter(prefix="/api/conversations", tags=["conversations"])

    @router.get("")
    def list_conversations(client_id: UUID = Header(alias="X-Client-ID")):
        with uow_factory() as uow:
            return [
                asdict(conversation)
                for conversation in history.list_conversations(uow, str(client_id))
            ]

    @router.post("", status_code=status.HTTP_201_CREATED)
    def create_conversation(
        request: CreateConversationRequest,
        client_id: UUID = Header(alias="X-Client-ID"),
    ):
        if not request.title.strip():
            raise HTTPException(status_code=422, detail="標題不可為空白")
        with uow_factory() as uow:
            return asdict(history.create_conversation(uow, str(client_id), request.title))

    @router.get("/{conversation_id}")
    def get_conversation(
        conversation_id: UUID,
        client_id: UUID = Header(alias="X-Client-ID"),
    ):
        try:
            with uow_factory() as uow:
                conversation, messages = history.get_conversation(
                    uow, str(client_id), str(conversation_id),
                )
        except ConversationNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {**asdict(conversation), "messages": [asdict(item) for item in messages]}

    return router
