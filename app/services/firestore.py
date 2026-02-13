from __future__ import annotations

import logging
from datetime import datetime

from google.cloud.firestore_v1.async_client import AsyncClient
from google.cloud.firestore_v1 import async_transactional
from google.cloud import firestore as firestore_types

from app.config import settings
from app.models.schemas import MessageRecord, SessionResponse, ToolCall

logger = logging.getLogger(__name__)


class SessionStore:
    def __init__(self) -> None:
        self._client: AsyncClient | None = None

    @property
    def client(self) -> AsyncClient:
        if self._client is None:
            self._client = AsyncClient(project=settings.GCP_PROJECT_ID)
        return self._client

    @property
    def collection(self):
        return self.client.collection(settings.FIRESTORE_COLLECTION)

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: list[ToolCall] | None = None,
        cost_usd: float = 0.0,
    ) -> None:
        doc_ref = self.collection.document(session_id)
        now = datetime.utcnow()

        msg_data = {
            "role": role,
            "content": content,
            "tool_calls": [tc.model_dump() for tc in (tool_calls or [])],
            "timestamp": now,
        }

        doc = await doc_ref.get()
        if doc.exists:
            await doc_ref.update({
                "messages": firestore_types.ArrayUnion([msg_data]),
                "updated_at": now,
                "total_cost_usd": firestore_types.Increment(cost_usd),
            })
        else:
            await doc_ref.set({
                "session_id": session_id,
                "messages": [msg_data],
                "created_at": now,
                "updated_at": now,
                "total_cost_usd": cost_usd,
            })

    async def get_session(self, session_id: str) -> SessionResponse | None:
        doc = await self.collection.document(session_id).get()
        if not doc.exists:
            return None

        data = doc.to_dict()
        messages = []
        for m in data.get("messages", []):
            messages.append(MessageRecord(
                role=m["role"],
                content=m["content"],
                tool_calls=[ToolCall(**tc) for tc in m.get("tool_calls", [])],
                timestamp=m.get("timestamp", datetime.utcnow()),
            ))

        return SessionResponse(
            session_id=data["session_id"],
            messages=messages,
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            total_cost_usd=data.get("total_cost_usd", 0.0),
        )

    async def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None


session_store = SessionStore()
