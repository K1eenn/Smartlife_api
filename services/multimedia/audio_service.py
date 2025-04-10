from __future__ import annotations

import re
import base64
import os
import uuid
from io import BytesIO
from typing import Dict, Any, Optional

from html import unescape
from gtts import gTTS
from openai import OpenAI

from config.logging_config import logger
from config.settings import TEMP_DIR

def process_audio(message_dict: Dict[str, Any], api_key: str) -> Optional[Dict[str, Any]]:
    """Chuyển đổi audio base64 sang text dùng Whisper."""
    try:
        if not message_dict.get("audio_data"):
            logger.error("process_audio: Thiếu audio_data.")
            return None
        audio_data = base64.b64decode(message_dict["audio_data"])

        temp_audio_path = os.path.join(TEMP_DIR, f"{uuid.uuid4()}.wav") # Assume wav for simplicity

        with open(temp_audio_path, "wb") as f:
            f.write(audio_data)

        client = OpenAI(api_key=api_key)
        with open(temp_audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )

        os.remove(temp_audio_path)

        return {"type": "text", "text": transcript.text}

    except base64.binascii.Error as b64_err:
        logger.error(f"Lỗi giải mã Base64 audio: {b64_err}")
        return None
    except Exception as e:
        logger.error(f"Lỗi khi xử lý audio: {e}", exc_info=True)
        if 'temp_audio_path' in locals() and os.path.exists(temp_audio_path):
             try: os.remove(temp_audio_path)
             except OSError: pass
        return None

def text_to_speech_google(text: str, lang: str = 'vi', slow: bool = False, max_length: int = 5000) -> Optional[str]:
    """Chuyển text thành audio base64 dùng gTTS."""
    try:
        clean_text = re.sub(r'<[^>]*>', ' ', text)
        clean_text = unescape(clean_text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        if not clean_text:
             logger.warning("TTS: Văn bản rỗng sau khi làm sạch.")
             return None

        if len(clean_text) > max_length:
            logger.warning(f"TTS: Văn bản quá dài ({len(clean_text)}), cắt ngắn còn {max_length}.")
            cut_pos = clean_text.rfind('.', 0, max_length)
            if cut_pos == -1: cut_pos = clean_text.rfind('?', 0, max_length)
            if cut_pos == -1: cut_pos = clean_text.rfind('!', 0, max_length)
            if cut_pos == -1 or cut_pos < max_length // 2: cut_pos = max_length
            clean_text = clean_text[:cut_pos+1]

        audio_buffer = BytesIO()
        tts = gTTS(text=clean_text, lang=lang, slow=slow)
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        audio_data = audio_buffer.read()
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        return audio_base64

    except Exception as e:
        logger.error(f"Lỗi khi sử dụng Google TTS: {e}", exc_info=True)
        return None