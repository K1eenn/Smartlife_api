from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional

from config.logging_config import logger
from database.data_manager import chat_history, family_data

router = APIRouter()

@router.get("/chat_history/{member_id}")
async def get_member_chat_history(member_id: str):
    """Lấy lịch sử chat của một thành viên."""
    if member_id in chat_history:
        return chat_history[member_id][:10]
    return []

@router.get("/chat_history/session/{session_id}")
async def get_session_chat_history(session_id: str):
    """Lấy lịch sử chat theo session_id (có thể chậm)."""
    session_chats = []
    for member_id, histories in chat_history.items():
        for history in histories:
            if history.get("session_id") == session_id:
                history_with_member = history.copy()
                history_with_member["member_id"] = member_id
                if member_id in family_data:
                    history_with_member["member_name"] = family_data[member_id].get("name", "")
                session_chats.append(history_with_member)
    session_chats.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return session_chats