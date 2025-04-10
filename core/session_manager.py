from __future__ import annotations

import os
import json
import datetime
import logging
from typing import Dict, Any, Optional

from config.settings import SESSIONS_DATA_FILE
from config.logging_config import logger

class SessionManager:
    """Quản lý session và trạng thái cho mỗi client với khả năng lưu trạng thái"""
    def __init__(self, sessions_file=SESSIONS_DATA_FILE): # Use constant
        self.sessions = {}
        self.sessions_file = sessions_file
        self._load_sessions()

    def _load_sessions(self):
        """Tải dữ liệu session từ file"""
        try:
            if os.path.exists(self.sessions_file):
                with open(self.sessions_file, "r", encoding="utf-8") as f:
                    loaded_sessions = json.load(f)
                    if isinstance(loaded_sessions, dict):
                        self.sessions = loaded_sessions
                        logger.info(f"Đã tải {len(self.sessions)} session từ {self.sessions_file}")
                    else:
                        logger.warning(f"Dữ liệu session trong {self.sessions_file} không hợp lệ (không phải dict), khởi tạo lại.")
                        self.sessions = {} # Reset if invalid structure
        except json.JSONDecodeError as e:
            logger.error(f"Lỗi JSON khi tải session từ {self.sessions_file}: {e}. Khởi tạo lại.")
            self.sessions = {} # Reset on JSON error
        except Exception as e:
            logger.error(f"Lỗi không xác định khi tải session: {e}", exc_info=True)
            self.sessions = {} # Reset on other errors


    def _save_sessions(self):
        """Lưu dữ liệu session vào file"""
        try:
            os.makedirs(os.path.dirname(self.sessions_file) or '.', exist_ok=True)
            with open(self.sessions_file, "w", encoding="utf-8") as f:
                json.dump(self.sessions, f, ensure_ascii=False, indent=2)
            logger.debug(f"Đã lưu {len(self.sessions)} session vào {self.sessions_file}") # Reduced log level
            return True
        except Exception as e:
            logger.error(f"Lỗi khi lưu session: {e}", exc_info=True)
            return False

    def get_session(self, session_id):
        """Lấy session hoặc tạo mới nếu chưa tồn tại"""
        if session_id not in self.sessions:
            logger.info(f"Tạo session mới: {session_id}")
            self.sessions[session_id] = {
                "messages": [],
                "current_member": None,
                "suggested_question": None,
                "process_suggested": False,
                "question_cache": {},
                "created_at": datetime.datetime.now().isoformat(),
                "last_updated": datetime.datetime.now().isoformat()
            }
            self._save_sessions() # Save immediately after creation
        return self.sessions[session_id]

    def update_session(self, session_id, data):
        """Cập nhật dữ liệu session"""
        if session_id in self.sessions:
            try:
                self.sessions[session_id].update(data)
                self.sessions[session_id]["last_updated"] = datetime.datetime.now().isoformat()
                # Consider saving less often if performance is an issue.
                if not self._save_sessions():
                     logger.error(f"Cập nhật session {session_id} thành công trong bộ nhớ nhưng LƯU THẤT BẠI.")
                return True
            except Exception as e:
                logger.error(f"Lỗi khi cập nhật session {session_id} trong bộ nhớ: {e}", exc_info=True)
                return False
        else:
             logger.warning(f"Cố gắng cập nhật session không tồn tại: {session_id}")
             return False

    def delete_session(self, session_id):
        """Xóa session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._save_sessions()
            logger.info(f"Đã xóa session: {session_id}")
            return True
        return False

    def cleanup_old_sessions(self, days_threshold=30):
        """Xóa các session cũ không hoạt động sau số ngày nhất định"""
        now = datetime.datetime.now(datetime.timezone.utc) # Use timezone-aware datetime
        sessions_to_remove = []
        removed_count = 0

        for session_id, session_data in list(self.sessions.items()): # Iterate over a copy
            last_updated_str = session_data.get("last_updated")
            if last_updated_str:
                try:
                    last_updated_date = datetime.datetime.fromisoformat(last_updated_str)
                    if last_updated_date.tzinfo is None:
                        # Assuming stored time is UTC, make it aware
                        last_updated_date = last_updated_date.replace(tzinfo=datetime.timezone.utc)

                    time_inactive = now - last_updated_date
                    if time_inactive.days > days_threshold:
                        sessions_to_remove.append(session_id)
                except ValueError:
                    logger.error(f"Định dạng last_updated không hợp lệ ('{last_updated_str}') cho session {session_id}. Xem xét xóa.")
                except Exception as e:
                    logger.error(f"Lỗi khi xử lý thời gian cho session {session_id}: {e}", exc_info=True)

        if sessions_to_remove:
             for session_id in sessions_to_remove:
                 if session_id in self.sessions:
                     del self.sessions[session_id]
                     removed_count += 1
             if removed_count > 0:
                 self._save_sessions()
                 logger.info(f"Đã xóa {removed_count} session cũ (quá {days_threshold} ngày không hoạt động).")
             else:
                  logger.info("Không có session cũ nào cần xóa.")
        else:
            logger.info("Không có session cũ nào cần xóa.")