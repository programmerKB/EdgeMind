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
from edgemind.infrastructure.persistence.models import ChatConversationRow, ChatMessageRow
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
        self.other_owner = str(uuid4())
        self.addCleanup(self.client.close)
        self.addCleanup(self.engine.dispose)

    def headers(self, owner=None):
        return {"X-Client-ID": owner or self.owner}

    def test_create_stream_and_reload_complete_timeline(self):
        created_response = self.client.post(
            "/api/conversations",
            headers=self.headers(),
            json={"title": "M1 狀態如何？"},
        )
        self.assertEqual(created_response.status_code, 201)
        created = created_response.json()
        self.assertEqual(created["title"], "M1 狀態如何？")
        self.assertEqual(
            self.client.get("/api/conversations", headers=self.headers()).json()[0]["id"],
            created["id"],
        )

        response = self.client.post(
            "/api/chat_utf8",
            headers=self.headers(),
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

        reloaded = self.client.get(
            "/api/conversations/" + created["id"], headers=self.headers(),
        )
        self.assertEqual(reloaded.status_code, 200)
        messages = reloaded.json()["messages"]
        self.assertEqual(
            [(item["role"], item["status"]) for item in messages],
            [("user", None), ("agent", "thought"), ("agent", "artifacts"), ("agent", "success")],
        )
        self.assertEqual(messages[0]["content"], "M1 狀態如何？")
        self.assertEqual(messages[2]["attachments"][0]["label"], "圖表")
        self.assertEqual(messages[3]["token_usage"]["total_tokens"], 8)

    def test_owner_isolation_and_missing_owner_header(self):
        created = self.client.post(
            "/api/conversations", headers=self.headers(), json={"title": "私有紀錄"},
        ).json()
        self.assertEqual(
            self.client.get("/api/conversations", headers=self.headers(self.other_owner)).json(),
            [],
        )
        self.assertEqual(
            self.client.get(
                "/api/conversations/" + created["id"],
                headers=self.headers(self.other_owner),
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                "/api/chat_utf8",
                headers=self.headers(self.other_owner),
                json={"conversation_id": created["id"], "message": "偷看"},
            ).status_code,
            404,
        )
        self.assertEqual(self.client.get("/api/conversations").status_code, 422)
        self.assertEqual(
            self.client.post(
                "/api/chat_utf8",
                json={"conversation_id": created["id"], "message": "漏了識別碼"},
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.get(
                "/api/conversations/" + created["id"], headers=self.headers(),
            ).json()["messages"],
            [],
        )
