"""Exercise the HTTP and SQL persistence path without Gemini or PostgreSQL."""

from functools import partial
import json
import unittest
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from edgemind.application.agent import AgentEvent, TokenUsage
from edgemind.application.chat_history import ChatHistoryService
from edgemind.infrastructure.persistence.database import Base
from edgemind.infrastructure.persistence.models import (
    ChatConversationRow,
    ChatMessageRow,
    utc_now,
)
from edgemind.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from edgemind.presentation.api.routes import chat, conversations


class FakeAgent:
    async def stream(self, message, inference_model):
        yield AgentEvent("thought", "正在分析")
        yield AgentEvent(
            "artifacts", "報表已產生",
            attachments=[{"url": "/api/report-artifacts/chart.svg", "label": "圖表"}],
        )
        yield AgentEvent(
            "success", "診斷完成",
            token_usage=TokenUsage(prompt_tokens=5, total_tokens=8),
        )


class ChatHistoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        factory = partial(
            SqlAlchemyUnitOfWork,
            sessionmaker(bind=self.engine, autoflush=False),
        )
        history = ChatHistoryService()
        app = FastAPI()
        app.include_router(conversations.create_router(history, factory))
        app.include_router(chat.create_router(FakeAgent(), history, factory))
        self.client = TestClient(app)
        self.owner = str(uuid4())
        self.addCleanup(self.client.close)
        self.addCleanup(self.engine.dispose)

    def test_create_stream_and_reload_complete_timeline(self):
        created_response = self.client.post(
            "/api/conversations",
            json={"title": "M1 狀態如何？"},
        )
        self.assertEqual(created_response.status_code, 201)
        created = created_response.json()
        self.assertEqual(created["title"], "M1 狀態如何？")
        self.assertEqual(
            self.client.get("/api/conversations").json()[0]["id"],
            created["id"],
        )

        response = self.client.post(
            "/api/chat_utf8",
            json={"conversation_id": created["id"], "message": "M1 狀態如何？"},
        )
        self.assertEqual(response.status_code, 200)
        frames = [
            json.loads(line.removeprefix("data: "))
            for line in response.text.splitlines() if line.startswith("data: ")
        ]
        self.assertEqual(
            [frame["status"] for frame in frames],
            ["thought", "artifacts", "success"],
        )

        reloaded = self.client.get("/api/conversations/" + created["id"])
        self.assertEqual(reloaded.status_code, 200)
        messages = reloaded.json()["messages"]
        self.assertEqual(
            [(item["role"], item["status"]) for item in messages],
            [("user", None), ("agent", "thought"), ("agent", "artifacts"), ("agent", "success")],
        )
        self.assertEqual(messages[0]["content"], "M1 狀態如何？")
        self.assertEqual(messages[2]["attachments"][0]["label"], "圖表")
        self.assertEqual(messages[3]["token_usage"]["total_tokens"], 8)

    def test_old_browser_histories_and_new_chats_are_shared(self):
        legacy_id = str(uuid4())
        second_legacy_id = str(uuid4())
        now = utc_now()
        with self.engine.begin() as connection:
            connection.execute(
                ChatConversationRow.__table__.insert(),
                [
                    {
                        "id": legacy_id, "owner_id": self.owner,
                        "title": "Chrome 舊紀錄",
                        "created_at": now, "updated_at": now,
                    },
                    {
                        "id": second_legacy_id, "owner_id": str(uuid4()),
                        "title": "Edge 舊紀錄",
                        "created_at": now, "updated_at": now,
                    },
                ],
            )

        created = self.client.post(
            "/api/conversations", json={"title": "新的共用紀錄"},
        ).json()
        listed = self.client.get(
            "/api/conversations",
            headers={"X-Client-ID": str(uuid4())},
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(
            {item["id"] for item in listed.json()},
            {legacy_id, second_legacy_id, created["id"]},
        )
        self.assertEqual(
            self.client.get("/api/conversations/" + legacy_id).json()["title"],
            "Chrome 舊紀錄",
        )
        self.assertEqual(
            self.client.get("/api/conversations/" + second_legacy_id).json()["title"],
            "Edge 舊紀錄",
        )
        response = self.client.post(
            "/api/chat_utf8",
            json={"conversation_id": legacy_id, "message": "繼續舊對話"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.get("/api/conversations/" + legacy_id)
            .json()["messages"][0]["content"],
            "繼續舊對話",
        )
        self.assertEqual(
            self.client.get("/api/conversations/" + str(uuid4())).status_code,
            404,
        )
