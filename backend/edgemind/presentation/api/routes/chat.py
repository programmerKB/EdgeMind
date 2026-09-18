"""SSE endpoints adapting transport-neutral Agent events to HTTP."""

import asyncio
from dataclasses import asdict
import logging
from typing import Callable
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from edgemind.application.agent import AgentEvent, AgentService
from edgemind.application.chat_history import ChatHistoryService, ConversationNotFound
from edgemind.application.ports import UnitOfWork
from edgemind.presentation.schemas import ChatRequest
from edgemind.presentation.sse import encode_sse_event


logger = logging.getLogger(__name__)


def create_router(
    agent: AgentService,
    history: ChatHistoryService,
    uow_factory: Callable[[], UnitOfWork],
) -> APIRouter:
    """Create chat routes bound to the Agent application service."""
    router = APIRouter(prefix="/api", tags=["agent"])

    async def stream(
        request: ChatRequest, client_id: UUID | None, *, ensure_ascii: bool,
    ) -> StreamingResponse:
        """Adapt application events to a non-buffered SSE response."""

        conversation_id = (
            str(request.conversation_id) if request.conversation_id else None
        )
        if conversation_id and client_id is None:
            raise HTTPException(status_code=422, detail="缺少 X-Client-ID")

        if conversation_id:
            def save_user_message():
                with uow_factory() as uow:
                    history.append_message(
                        uow, str(client_id), conversation_id,
                        role="user", content=request.message,
                    )

            try:
                await asyncio.to_thread(save_user_message)
            except ConversationNotFound as error:
                raise HTTPException(status_code=404, detail=str(error)) from error

        async def encoded_events():
            """Encode each transport-neutral Agent event as an SSE frame."""
            async for event in agent.stream(
                request.message,
                request.inference_model,
            ):
                if conversation_id:
                    def save_event():
                        with uow_factory() as uow:
                            history.append_message(
                                uow, str(client_id), conversation_id,
                                role="agent", content=event.content,
                                status=event.status,
                                attachments=event.attachments,
                                token_usage=(
                                    asdict(event.token_usage)
                                    if event.token_usage is not None else None
                                ),
                            )

                    try:
                        await asyncio.to_thread(save_event)
                    except Exception:
                        logger.exception("Failed to persist Agent chat event")
                        yield encode_sse_event(
                            AgentEvent("error", "聊天紀錄儲存失敗，請稍後重試。"),
                            ensure_ascii,
                        )
                        return
                yield encode_sse_event(event, ensure_ascii)

        return StreamingResponse(
            encoded_events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @router.post("/chat")
    async def chat_with_agent(
        request: ChatRequest,
        client_id: UUID | None = Header(default=None, alias="X-Client-ID"),
    ):
        """Stream an ASCII-escaped response for legacy clients."""
        return await stream(request, client_id, ensure_ascii=True)

    @router.post("/chat_utf8")
    async def chat_with_agent_utf8(
        request: ChatRequest,
        client_id: UUID | None = Header(default=None, alias="X-Client-ID"),
    ):
        """Stream native UTF-8 events for the React client."""
        return await stream(request, client_id, ensure_ascii=False)

    return router
