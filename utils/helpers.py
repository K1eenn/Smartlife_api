from __future__ import annotations

import re
import json
import random
import hashlib
import datetime
import asyncio
from typing import Dict, Any, List, Optional

from openai import OpenAI

from config.logging_config import logger
from config.settings import openai_model, CHAT_HISTORY_FILE
from database.data_manager import save_data, chat_history, family_data

async def generate_chat_summary(messages: List[Dict[str, Any]], api_key: str) -> str:
    """Tạo tóm tắt từ lịch sử trò chuyện (async wrapper)."""
    if not api_key or not messages or len(messages) < 2:
        return "Chưa đủ nội dung để tóm tắt."

    conversation_text = ""
    for msg in messages[-10:]:
        role = msg.get("role")
        content = msg.get("content")
        text_content = ""
        if isinstance(content, str):
            text_content = content
        elif isinstance(content, list):
             for item in content:
                  if isinstance(item, dict) and item.get("type") == "text":
                       text_content += item.get("text", "") + " "
        elif role == "tool":
             text_content = f"[Tool {msg.get('name')} result: {str(content)[:50]}...]"

        if role and text_content:
             conversation_text += f"{role.capitalize()}: {text_content.strip()}\n"

    if not conversation_text: return "Không có nội dung text để tóm tắt."


    try:
        client = OpenAI(api_key=api_key)
        response = await asyncio.to_thread(
             client.chat.completions.create,
             model=openai_model,
             messages=[
                 {"role": "system", "content": "Tóm tắt cuộc trò chuyện sau thành 1 câu ngắn gọn bằng tiếng Việt, nêu bật yêu cầu chính hoặc kết quả cuối cùng."},
                 {"role": "user", "content": conversation_text}
             ],
             temperature=0.2,
             max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Lỗi khi tạo tóm tắt chat: {e}", exc_info=True)
        return "[Lỗi tóm tắt]"


def save_chat_history(member_id: str, messages: List[Dict[str, Any]], summary: Optional[str] = None, session_id: Optional[str] = None) -> None:
    """Lưu lịch sử chat cho member_id."""
    global chat_history
    if not member_id: return

    if member_id not in chat_history or not isinstance(chat_history[member_id], list):
        chat_history[member_id] = []

    history_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "messages": messages,
        "summary": summary or "",
        "session_id": session_id
    }

    chat_history[member_id].insert(0, history_entry)

    max_history_per_member = 20
    if len(chat_history[member_id]) > max_history_per_member:
        chat_history[member_id] = chat_history[member_id][:max_history_per_member]

    if not save_data(CHAT_HISTORY_FILE, chat_history):
        logger.error(f"Lưu lịch sử chat cho member {member_id} thất bại.")


def generate_dynamic_suggested_questions(api_key: str, member_id: Optional[str] = None, max_questions: int = 5) -> List[str]:
    """Tạo câu hỏi gợi ý động (sử dụng mẫu câu)."""
    logger.info("Sử dụng phương pháp mẫu câu để tạo câu hỏi gợi ý")

    random_seed = int(hashlib.md5(f"{datetime.datetime.now().strftime('%Y-%m-%d_%H')}_{member_id or 'guest'}".encode()).hexdigest(), 16)
    random.seed(random_seed)

    question_templates = {
        "news": [ "Tin tức {topic} mới nhất?", "Có gì mới về {topic} hôm nay?", "Điểm tin {topic} sáng nay?", "Cập nhật tình hình {topic}?" ],
        # Removed "weather" category
        "events": [ "Sự kiện nổi bật tuần này?", "Lịch chiếu phim {cinema}?", "Trận đấu {team} tối nay mấy giờ?", "Có hoạt động gì thú vị cuối tuần?" ],
        "food": [ "Công thức nấu món {dish}?", "Quán {dish} ngon ở {district}?", "Cách làm {dessert} đơn giản?" ],
        "hobbies": [ "Sách hay về chủ đề {genre}?", "Mẹo chụp ảnh đẹp bằng điện thoại?", "Bài tập yoga giảm căng thẳng?" ],
        "general": [ "Kể một câu chuyện cười?", "Đố vui về {category}?", "Hôm nay có ngày gì đặc biệt?", "Cho tôi một lời khuyên ngẫu nhiên?", "Ý tưởng làm gì khi rảnh?" ]
    }

    prefs = {}
    if member_id and member_id in family_data:
         prefs = family_data[member_id].get("preferences", {})

    replacements = {
        "topic": ["thế giới", "kinh tế", "thể thao", "giải trí", "công nghệ", "giáo dục", "y tế", prefs.get("hobby", "khoa học")],
        # Removed "location" as it was mainly for weather
        "cinema": ["CGV", "Lotte", "BHD", "Galaxy"],
        "team": [prefs.get("team", "Việt Nam"), "Man City", "Real Madrid", "Arsenal"],
        "dish": [prefs.get("food", "phở"), "bún chả", "cơm tấm", "pizza", "sushi"],
        "district": ["quận 1", "Hoàn Kiếm", "Hải Châu", "gần đây"],
        "dessert": ["chè", "bánh flan", "rau câu"],
        "genre": [prefs.get("book_genre", "trinh thám"), "lịch sử", "khoa học viễn tưởng", "tâm lý"],
        "category": ["động vật", "lịch sử", "khoa học", "phim ảnh"]
    }

    all_questions = []
    categories = list(question_templates.keys())
    random.shuffle(categories)

    for category in categories:
        template = random.choice(question_templates[category])
        question = template
        placeholder_match = re.search(r'\{(\w+)\}', question)
        while placeholder_match:
             key = placeholder_match.group(1)
             if key in replacements:
                  replacement = random.choice(replacements[key])
                  question = question.replace(placeholder_match.group(0), replacement, 1)
             else:
                  question = question.replace(placeholder_match.group(0), "...", 1)
             placeholder_match = re.search(r'\{(\w+)\}', question)
        all_questions.append(question)

    final_suggestions = []
    seen_suggestions = set()
    for q in all_questions:
         if len(final_suggestions) >= max_questions: break
         if q not in seen_suggestions:
              final_suggestions.append(q)
              seen_suggestions.add(q)

    while len(final_suggestions) < max_questions and len(final_suggestions) < len(all_questions):
         q = random.choice(all_questions)
         if q not in seen_suggestions:
              final_suggestions.append(q)
              seen_suggestions.add(q)

    logger.info(f"Đã tạo {len(final_suggestions)} câu hỏi gợi ý bằng mẫu.")
    return final_suggestions


def filter_events_by_member(member_id: Optional[str] = None) -> Dict[str, Any]:
    """Lọc sự kiện theo thành viên (người tạo hoặc tham gia)."""
    from database.data_manager import events_data
    
    if not member_id: return events_data

    filtered = {}
    member_name = family_data.get(member_id, {}).get("name") if member_id in family_data else None

    for event_id, event in events_data.items():
        is_creator = event.get("created_by") == member_id
        is_participant = member_name and (member_name in event.get("participants", []))

        if is_creator or is_participant:
            filtered[event_id] = event
    return filtered