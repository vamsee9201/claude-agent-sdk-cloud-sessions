from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ToolCall(BaseModel):
    tool_name: str
    tool_input: dict
    tool_result: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    response_text: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    is_error: bool = False
    cost_usd: float | None = None
    duration_ms: int | None = None


class MessageRecord(BaseModel):
    role: str
    content: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionResponse(BaseModel):
    session_id: str
    messages: list[MessageRecord] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    total_cost_usd: float = 0.0
