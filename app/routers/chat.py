import logging
import time

from fastapi import APIRouter, HTTPException

from app.models.schemas import ChatRequest, ChatResponse
from app.services.agent import run_agent
from app.services.firestore import session_store

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    start = time.time()

    result = await run_agent(
        message=request.message,
        session_id=request.session_id,
    )

    if not result.session_id:
        raise HTTPException(status_code=500, detail="Agent did not return a session ID")

    # Save user message to Firestore
    await session_store.save_message(
        session_id=result.session_id,
        role="user",
        content=request.message,
    )

    # Save assistant message to Firestore
    await session_store.save_message(
        session_id=result.session_id,
        role="assistant",
        content=result.response_text,
        tool_calls=result.tool_calls,
        cost_usd=result.cost_usd or 0.0,
    )

    return ChatResponse(
        session_id=result.session_id,
        response_text=result.response_text,
        tool_calls=result.tool_calls,
        is_error=result.is_error,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms or int((time.time() - start) * 1000),
    )
