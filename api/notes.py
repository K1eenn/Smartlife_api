from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional

from config.logging_config import logger
from models.schemas import NoteModel
from database.data_manager import notes_data
from services.tools.note_tools import add_note

router = APIRouter()

@router.get("/notes")
async def get_notes(member_id: Optional[str] = None):
    if member_id:
        return {note_id: note for note_id, note in notes_data.items()
                if note.get("created_by") == member_id}
    return notes_data

@router.post("/notes")
async def add_note_endpoint(note: NoteModel, member_id: Optional[str] = None):
    """Thêm ghi chú (qua endpoint trực tiếp)."""
    details = note.dict()
    details["created_by"] = member_id
    if add_note(details):
         new_note_id = None
         for nid, ndata in notes_data.items():
              if (ndata.get("title") == note.title and
                  ndata.get("content") == note.content and
                  ndata.get("created_by") == member_id):
                   new_note_id = nid
                   break
         if new_note_id:
              return {"id": new_note_id, "note": notes_data[new_note_id]}
         else:
              raise HTTPException(status_code=500, detail="Thêm note thành công nhưng không tìm thấy ID.")
    else:
        raise HTTPException(status_code=500, detail="Không thể thêm ghi chú.")