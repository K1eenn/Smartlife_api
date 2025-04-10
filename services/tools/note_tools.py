from __future__ import annotations

import uuid
import datetime
from typing import Dict, Any, Optional, List

from config.logging_config import logger
from database.data_manager import notes_data, save_data
from config.settings import NOTES_DATA_FILE

def add_note(details: Dict[str, Any]) -> bool:
    """Thêm ghi chú mới."""
    global notes_data
    try:
        note_id = str(uuid.uuid4())
        if not details.get("title") or not details.get("content"):
             logger.error(f"Thiếu title hoặc content khi thêm note: {details}")
             return False

        notes_data[note_id] = {
            "id": note_id,
            "title": details.get("title"),
            "content": details.get("content"),
            "tags": details.get("tags", []),
            "created_by": details.get("created_by"),
            "created_on": datetime.datetime.now().isoformat()
        }
        if save_data(NOTES_DATA_FILE, notes_data):
            logger.info(f"Đã thêm ghi chú ID {note_id}: {details.get('title')}")
            return True
        else:
             logger.error(f"Lưu thất bại sau khi thêm note {note_id} vào bộ nhớ.")
             if note_id in notes_data: del notes_data[note_id]
             return False
    except Exception as e:
         logger.error(f"Lỗi khi thêm note: {e}", exc_info=True)
         return False