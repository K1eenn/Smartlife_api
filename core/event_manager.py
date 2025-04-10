from __future__ import annotations

import re
from typing import Dict, Optional, List

from config.logging_config import logger

# Phân loại sự kiện
EVENT_CATEGORIES = {
    "Health": ["khám sức khỏe", "uống thuốc", "bác sĩ", "nha sĩ", "tái khám", "tập luyện", "gym", "yoga", "chạy bộ", "thể dục"],
    "Study": ["học", "lớp học", "ôn tập", "bài tập", "deadline", "thuyết trình", "seminar", "workshop", "thi", "kiểm tra"],
    "Meeting": ["họp", "hội nghị", "phỏng vấn", "gặp mặt", "trao đổi", "thảo luận", "team sync", "standup", "meeting"],
    "Travel": ["bay", "chuyến bay", "tàu", "xe", "đi công tác", "du lịch", "sân bay", "ga tàu", "di chuyển", "check-in", "check-out"],
    "Event": ["sinh nhật", "kỷ niệm", "lễ", "tiệc", "liên hoan", "đám cưới", "đám hỏi", "ăn mừng", "tụ tập", "sum họp", "event"],
    "Personal": ["riêng tư", "cá nhân", "sở thích", "đọc sách", "xem phim", "thời gian riêng", "cắt tóc", "spa", "làm đẹp"],
    "Reminder": ["nhắc", "nhớ", "mua", "gọi điện", "thanh toán", "đặt lịch", "nộp", "đến hạn", "chuyển tiền", "lấy đồ"],
    "Break": ["nghỉ ngơi", "thư giãn", "giải lao", "ăn trưa", "ăn tối", "ngủ trưa", "nghỉ phép"],
    # Thêm một category mặc định cuối cùng
    "General": [] # Dùng làm fallback
}

# Ưu tiên các category cụ thể hơn
CATEGORY_PRIORITY = [
    "Health", "Study", "Meeting", "Travel", "Reminder", "Event", "Personal", "Break", "General"
]

def classify_event(title: str, description: Optional[str]) -> str:
    """
    Phân loại sự kiện vào một category dựa trên tiêu đề và mô tả.
    """
    if not title:
        return "General" # Không có tiêu đề thì khó phân loại

    combined_text = title.lower()
    if description:
        combined_text += " " + description.lower()

    logger.debug(f"Classifying event with text: '{combined_text[:100]}...'")

    for category in CATEGORY_PRIORITY:
        keywords = EVENT_CATEGORIES.get(category, [])
        if not keywords and category != "General": # Bỏ qua nếu category (trừ General) không có keyword
             continue
        # Kiểm tra các keywords của category hiện tại
        for keyword in keywords:
            # Sử dụng regex để tìm từ khóa đứng riêng lẻ (word boundary)
            if re.search(r'\b' + re.escape(keyword) + r'\b', combined_text):
                logger.info(f"Event classified as '{category}' based on keyword '{keyword}'")
                return category

    # Nếu không khớp với category nào có keyword, trả về General
    logger.info(f"Event could not be specifically classified, defaulting to 'General'")
    return "General"