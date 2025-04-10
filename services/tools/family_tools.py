from __future__ import annotations

import uuid
import datetime
from typing import Dict, Any, Optional, List

from config.logging_config import logger
from database.data_manager import family_data, save_data
from config.settings import FAMILY_DATA_FILE

def add_family_member(details: Dict[str, Any]) -> bool:
    """Thêm thành viên mới."""
    global family_data
    try:
        member_id = str(uuid.uuid4())
        if not details.get("name"):
             logger.error("Không thể thêm thành viên: thiếu tên.")
             return False
        family_data[member_id] = {
            "id": member_id,
            "name": details.get("name"),
            "age": details.get("age", ""),
            "preferences": details.get("preferences", {}),
            "added_on": datetime.datetime.now().isoformat()
        }
        if save_data(FAMILY_DATA_FILE, family_data):
             logger.info(f"Đã thêm thành viên ID {member_id}: {details.get('name')}")
             return True
        else:
             logger.error(f"Lưu thất bại sau khi thêm thành viên {member_id} vào bộ nhớ.")
             if member_id in family_data: del family_data[member_id]
             return False
    except Exception as e:
         logger.error(f"Lỗi khi thêm thành viên: {e}", exc_info=True)
         return False

def update_preference(details: Dict[str, Any]) -> bool:
    """Cập nhật sở thích."""
    global family_data
    try:
        member_id = str(details.get("member_id"))
        preference_key = details.get("preference_key")
        preference_value = details.get("preference_value")

        if not member_id or not preference_key or preference_value is None:
             logger.error(f"Thiếu thông tin để cập nhật sở thích: {details}")
             return False

        if member_id in family_data:
            if "preferences" not in family_data[member_id] or not isinstance(family_data[member_id]["preferences"], dict):
                family_data[member_id]["preferences"] = {}

            original_value = family_data[member_id]["preferences"].get(preference_key)
            family_data[member_id]["preferences"][preference_key] = preference_value
            family_data[member_id]["last_updated"] = datetime.datetime.now().isoformat()

            if save_data(FAMILY_DATA_FILE, family_data):
                logger.info(f"Đã cập nhật sở thích '{preference_key}' cho thành viên {member_id}")
                return True
            else:
                 logger.error(f"Lưu thất bại sau khi cập nhật sở thích cho {member_id}.")
                 if original_value is not None:
                      family_data[member_id]["preferences"][preference_key] = original_value
                 else:
                      if preference_key in family_data[member_id]["preferences"]:
                           del family_data[member_id]["preferences"][preference_key]
                 return False
        else:
            logger.warning(f"Không tìm thấy thành viên ID={member_id} để cập nhật sở thích.")
            return False
    except Exception as e:
         logger.error(f"Lỗi khi cập nhật sở thích: {e}", exc_info=True)
         return False