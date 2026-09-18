"""SQLAlchemy adapter for shared conversations and chat messages."""

from uuid import uuid4

from sqlalchemy.orm import Session

from edgemind.domain.entities import ChatConversation, ChatMessage
from edgemind.infrastructure.persistence.models import (
    ChatConversationRow,
    ChatMessageRow,
    utc_now,
)

# Existing rows retain their browser UUIDs; new rows use this shared marker.
# Reads intentionally ignore owner_id so earlier histories remain visible.
SHARED_OWNER_ID = "shared"


def _conversation(row: ChatConversationRow) -> ChatConversation:
    return ChatConversation(row.id, row.title, row.created_at, row.updated_at)


def _message(row: ChatMessageRow) -> ChatMessage:
    return ChatMessage(
        row.id,
        row.role,
        row.content,
        row.status,
        row.attachments or [],
        row.token_usage,
        row.created_at,
    )


class SqlAlchemyChatRepository:
    """Store one timeline shared by everyone using this deployment."""

    def __init__(self, session: Session):
        self._session = session

    def list_conversations(self) -> list[ChatConversation]:
        rows = (
            self._session.query(ChatConversationRow)
            .order_by(ChatConversationRow.updated_at.desc(), ChatConversationRow.id.desc())
            .all()
        )
        return [_conversation(row) for row in rows]

    def create_conversation(self, title: str) -> ChatConversation:
        now = utc_now()
        row = ChatConversationRow(
            id=str(uuid4()), owner_id=SHARED_OWNER_ID, title=title,
            created_at=now, updated_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return _conversation(row)

    def get_conversation(self, conversation_id: str) -> ChatConversation | None:
        row = (
            self._session.query(ChatConversationRow)
            .filter(ChatConversationRow.id == conversation_id)
            .first()
        )
        return _conversation(row) if row is not None else None

    def list_messages(self, conversation_id: str) -> list[ChatMessage]:
        rows = (
            self._session.query(ChatMessageRow)
            .filter(ChatMessageRow.conversation_id == conversation_id)
            .order_by(ChatMessageRow.id.asc())
            .all()
        )
        return [_message(row) for row in rows]

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        status: str | None,
        attachments: list[dict],
        token_usage: dict | None,
    ) -> ChatMessage:
        now = utc_now()
        row = ChatMessageRow(
            conversation_id=conversation_id, role=role, content=content,
            status=status, attachments=attachments, token_usage=token_usage,
            created_at=now,
        )
        self._session.add(row)
        self._session.query(ChatConversationRow).filter(
            ChatConversationRow.id == conversation_id,
        ).update({"updated_at": now})
        self._session.flush()
        return _message(row)
