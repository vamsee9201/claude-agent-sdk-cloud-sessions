from fastapi import APIRouter, HTTPException

from app.models.schemas import SessionResponse
from app.services.firestore import session_store

router = APIRouter()


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    session = await session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
