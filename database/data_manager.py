from __future__ import annotations

import os
import json
import shutil
from typing import Dict, Any, Optional

from config.settings import (
    FAMILY_DATA_FILE, EVENTS_DATA_FILE, NOTES_DATA_FILE, CHAT_HISTORY_FILE
)
from config.logging_config import logger

# Global data containers
family_data: Dict[str, Any] = {}
events_data: Dict[str, Any] = {}
notes_data: Dict[str, Any] = {}
chat_history: Dict[str, Any] = {}

def load_data(file_path: str) -> Dict[str, Any]:
    """
    Load data from JSON file.
    Returns empty dict if file does not exist or error occurs.
    """
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                     logger.warning(f"Dữ liệu trong {file_path} không phải từ điển. Khởi tạo lại.")
                     return {}
                return data
        except json.JSONDecodeError as e:
            logger.error(f"Lỗi JSON khi đọc {file_path}: {e}. Trả về dữ liệu trống.")
            return {}
        except Exception as e:
            logger.error(f"Lỗi không xác định khi đọc {file_path}: {e}", exc_info=True)
            return {}
    return {}

def save_data(file_path: str, data: Dict[str, Any]) -> bool:
    """
    Save data to JSON file.
    Returns True if successful, False otherwise.
    """
    try:
        os.makedirs(os.path.dirname(file_path) or '.', exist_ok=True)
        temp_file_path = file_path + ".tmp"
        with open(temp_file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        shutil.move(temp_file_path, file_path)
        return True
    except Exception as e:
        logger.error(f"Lỗi khi lưu dữ liệu vào {file_path}: {e}", exc_info=True)
        if os.path.exists(temp_file_path):
             try: os.remove(temp_file_path)
             except OSError as rm_err: logger.error(f"Không thể xóa file tạm {temp_file_path}: {rm_err}")
        return False

def verify_data_structure():
    """Kiểm tra và đảm bảo cấu trúc dữ liệu ban đầu."""
    global family_data, events_data, notes_data, chat_history
    needs_save = False

    if not isinstance(family_data, dict):
        logger.warning("family_data không phải từ điển. Khởi tạo lại.")
        family_data = {}
        needs_save = True

    if not isinstance(events_data, dict):
        logger.warning("events_data không phải từ điển. Khởi tạo lại.")
        events_data = {}
        needs_save = True

    if not isinstance(notes_data, dict):
        logger.warning("notes_data không phải từ điển. Khởi tạo lại.")
        notes_data = {}
        needs_save = True

    if not isinstance(chat_history, dict):
        logger.warning("chat_history không phải từ điển. Khởi tạo lại.")
        chat_history = {}
        needs_save = True

    if needs_save:
        logger.info("Lưu lại cấu trúc dữ liệu mặc định do phát hiện lỗi.")
        save_data(FAMILY_DATA_FILE, family_data)
        save_data(EVENTS_DATA_FILE, events_data)
        save_data(NOTES_DATA_FILE, notes_data)
        save_data(CHAT_HISTORY_FILE, chat_history)

def load_all_data():
    """Load all data from files"""
    global family_data, events_data, notes_data, chat_history
    
    family_data = load_data(FAMILY_DATA_FILE)
    events_data = load_data(EVENTS_DATA_FILE)
    notes_data = load_data(NOTES_DATA_FILE)
    chat_history = load_data(CHAT_HISTORY_FILE)
    verify_data_structure()