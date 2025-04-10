from __future__ import annotations

import uuid
import datetime
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional

from config.logging_config import logger
from models.schemas import SuggestedQuestionsResponse
from core.session_manager import session_manager
from utils.helpers import generate_dynamic_suggested_questions

router = APIRouter()

@router.post("/session")
async def create_session():
    session_id = str(uuid.uuid4())
    session_manager.get_session(session_id) # Creates if not exists
    return {"session_id": session_id}

@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    if session_manager.delete_session(session_id):
        return {"status": "success", "message": f"Đã xóa session {session_id}"}
    raise HTTPException(status_code=404, detail="Session không tồn tại")

@router.get("/sessions")
async def list_sessions():
    sessions_info = {}
    for session_id, session_data in session_manager.sessions.items():
        sessions_info[session_id] = {
            "created_at": session_data.get("created_at"),
            "last_updated": session_data.get("last_updated"),
            "member_id": session_data.get("current_member"),
            "message_count": len(session_data.get("messages", [])),
        }
    sorted_sessions = sorted(sessions_info.items(), key=lambda item: item[1].get('last_updated', ''), reverse=True)
    return dict(sorted_sessions)


@router.delete("/cleanup_sessions")
async def cleanup_old_sessions_endpoint(days: int = 30):
    try:
         session_manager.cleanup_old_sessions(days_threshold=days)
         return {"status": "success", "message": f"Đã bắt đầu dọn dẹp sessions không hoạt động trên {days} ngày"}
    except Exception as e:
         logger.error(f"Lỗi khi dọn dẹp session: {e}", exc_info=True)
         raise HTTPException(status_code=500, detail=f"Lỗi dọn dẹp session: {str(e)}")

@router.get("/suggested_questions")
async def get_suggested_questions(
    session_id: str,
    member_id: Optional[str] = None,
    openai_api_key: Optional[str] = None
):
    """Lấy câu hỏi gợi ý."""
    api_key = openai_api_key or os.getenv("OPENAI_API_KEY", "")
    session = session_manager.get_session(session_id)
    current_member_id = member_id or session.get("current_member")

    suggested_questions = generate_dynamic_suggested_questions(api_key, current_member_id, max_questions=5)
    current_timestamp = datetime.datetime.now().isoformat()

    session["suggested_question"] = suggested_questions
    session["question_timestamp"] = current_timestamp
    session_manager.update_session(session_id, session)

    return SuggestedQuestionsResponse(
        session_id=session_id,
        member_id=current_member_id,
        suggested_questions=suggested_questions,
        timestamp=current_timestamp
    )

@router.get("/cached_suggested_questions")
async def get_cached_suggested_questions(session_id: str):
    """Lấy câu hỏi gợi ý đã cache trong session."""
    session = session_manager.get_session(session_id)
    suggested = session.get("suggested_question", [])
    timestamp = session.get("question_timestamp", datetime.datetime.now().isoformat())
    return SuggestedQuestionsResponse(
        session_id=session_id,
        member_id=session.get("current_member"),
        suggested_questions=suggested,
        timestamp=timestamp
    )