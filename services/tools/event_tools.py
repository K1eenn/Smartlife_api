from __future__ import annotations

import uuid
import datetime
import re
from typing import Dict, Any, Optional, List

from config.logging_config import logger
from database.data_manager import events_data, save_data
from config.settings import EVENTS_DATA_FILE
from core.event_manager import classify_event

def add_event(details):
    """Thêm một sự kiện mới. Expects 'date' to be calculated YYYY-MM-DD."""
    global events_data
    try:
        event_id = str(uuid.uuid4())
        # Kiểm tra các trường bắt buộc cơ bản
        if not details.get('title') or ('date' not in details and details.get("repeat_type", "ONCE") == "ONCE"): # Cần date nếu là ONCE
            logger.error(f"Thiếu title hoặc date (cho sự kiện ONCE) khi thêm sự kiện: {details}")
            return False

        # Lấy category từ details, nếu không có thì dùng mặc định 'General'
        category = details.get("category", "General") # Lấy category đã được phân loại
        logger.info(f"Adding event with category: {category}")

        events_data[event_id] = {
            "id": event_id,
            "title": details.get("title"),
            "date": details.get("date"), # Có thể là None nếu là RECURRING không rõ ngày bắt đầu
            "time": details.get("time", "19:00"),
            "description": details.get("description", ""),
            "participants": details.get("participants", []),
            "repeat_type": details.get("repeat_type", "ONCE"),
            "category": category, # <<< THÊM CATEGORY VÀO ĐÂY
            "created_by": details.get("created_by"),
            "created_on": datetime.datetime.now().isoformat()
        }
        if save_data(EVENTS_DATA_FILE, events_data):
             logger.info(f"Đã thêm sự kiện ID {event_id}: {details.get('title')} (Category: {category})")
             return True
        else:
             logger.error(f"Lưu sự kiện ID {event_id} thất bại.")
             if event_id in events_data: del events_data[event_id]
             return False
    except Exception as e:
        logger.error(f"Lỗi nghiêm trọng khi thêm sự kiện: {e}", exc_info=True)
        return False

def update_event(details):
    """Cập nhật sự kiện. Expects 'date' to be calculated YYYY-MM-DD if provided."""
    global events_data
    event_id_str = str(details.get("id"))
    original_event_copy = None

    try:
        if not event_id_str or event_id_str not in events_data:
            logger.warning(f"Không tìm thấy sự kiện ID={event_id_str} để cập nhật.")
            return False

        original_event_copy = events_data.get(event_id_str, {}).copy()
        if not original_event_copy:
             logger.error(f"Không thể tạo bản sao cho event ID {event_id_str}.")
             return False

        updated = False
        event_to_update = events_data[event_id_str]

        for key, value in details.items():
            if key == "id": continue
            current_value = event_to_update.get(key)
            if value != current_value:
                if key == 'date' and not value and event_to_update.get("repeat_type", "ONCE") == "ONCE": # Chỉ cảnh báo nếu là ONCE và date bị xóa
                    logger.warning(f"Bỏ qua cập nhật date thành giá trị rỗng cho event ONCE ID {event_id_str}")
                    continue
                event_to_update[key] = value
                updated = True
                logger.debug(f"Event {event_id_str}: Updated field '{key}' to '{value}'") # Log giá trị mới

        if updated:
            # Lấy category mới nếu có, nếu không giữ nguyên category cũ
            new_category = details.get("category", event_to_update.get("category", "General"))
            if event_to_update.get("category") != new_category:
                 event_to_update["category"] = new_category
                 logger.info(f"Event {event_id_str}: Category updated to '{new_category}'")
            else:
                 logger.debug(f"Event {event_id_str}: Category remains '{new_category}'")

            event_to_update["last_updated"] = datetime.datetime.now().isoformat()
            logger.info(f"Attempting to save updated event ID={event_id_str}")
            if save_data(EVENTS_DATA_FILE, events_data):
                logger.info(f"Đã cập nhật và lưu thành công sự kiện ID={event_id_str}")
                return True
            else:
                 logger.error(f"Lưu cập nhật sự kiện ID {event_id_str} thất bại.")
                 if event_id_str in events_data and original_event_copy:
                      events_data[event_id_str] = original_event_copy
                      logger.info(f"Đã rollback thay đổi trong bộ nhớ cho event ID {event_id_str} do lưu thất bại.")
                 return False
        else:
             logger.info(f"Không có thay đổi nào được áp dụng cho sự kiện ID={event_id_str}")
             return True # No changes is success

    except Exception as e:
        logger.error(f"Lỗi nghiêm trọng khi cập nhật sự kiện ID {details.get('id')}: {e}", exc_info=True)
        if event_id_str and event_id_str in events_data and original_event_copy:
             events_data[event_id_str] = original_event_copy
             logger.info(f"Đã rollback thay đổi trong bộ nhớ cho event ID {event_id_str} do lỗi xử lý.")
        return False

def delete_event(details):
    """Xóa sự kiện dựa trên ID trong details dict."""
    global events_data
    event_id_to_delete = str(details.get("event_id"))
    if not event_id_to_delete:
         logger.error("Thiếu event_id để xóa sự kiện.")
         return False
    try:
        if event_id_to_delete in events_data:
            deleted_event_copy = events_data.pop(event_id_to_delete)
            if save_data(EVENTS_DATA_FILE, events_data):
                 logger.info(f"Đã xóa sự kiện ID {event_id_to_delete}")
                 return True
            else:
                 logger.error(f"Lưu sau khi xóa sự kiện ID {event_id_to_delete} thất bại.")
                 events_data[event_id_to_delete] = deleted_event_copy
                 logger.info(f"Đã rollback xóa trong bộ nhớ cho event ID {event_id_to_delete}.")
                 return False
        else:
            logger.warning(f"Không tìm thấy sự kiện ID {event_id_to_delete} để xóa.")
            return False
    except Exception as e:
         logger.error(f"Lỗi khi xóa sự kiện ID {event_id_to_delete}: {e}", exc_info=True)
         return False