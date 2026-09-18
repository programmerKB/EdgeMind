"""Conversation use cases independent from HTTP and SQLAlchemy."""

from edgemind.application.ports import UnitOfWork
from edgemind.domain.entities import ChatConversation, ChatMessage


class ConversationNotFound(ValueError):
    """The conversation does not exist for this browser identifier."""


class ChatHistoryService:
    """Coordinate ownership checks and durable chat writes."""

    def list_conversations(self, uow: UnitOfWork) -> list[ChatConversation]:
        return uow.chats.list_conversations()

    def create_conversation(
        self, uow: UnitOfWork, title: str,
    ) -> ChatConversation:
        conversation = uow.chats.create_conversation(title.strip()[:100])
        uow.commit()
        return conversation

    def get_conversation(
        self, uow: UnitOfWork, conversation_id: str,
    ) -> tuple[ChatConversation, list[ChatMessage]]:
        conversation = uow.chats.get_conversation(conversation_id)
        if conversation is None:
            raise ConversationNotFound("找不到這筆診斷紀錄")
        return conversation, uow.chats.list_messages(conversation_id)

    def append_message(
        self,
        uow: UnitOfWork,
        conversation_id: str,
        *,
        role: str,
        content: str,
        status: str | None = None,
        attachments: list[dict] | None = None,
        token_usage: dict | None = None,
    ) -> ChatMessage:
        if uow.chats.get_conversation(conversation_id) is None:
            raise ConversationNotFound("找不到這筆診斷紀錄")
        message = uow.chats.add_message(
            conversation_id, role, content, status, attachments or [], token_usage,
        )
        uow.commit()
        return message
