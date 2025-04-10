from __future__ import annotations

import os
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from typing import Dict, Any, List, Optional

from config.logging_config import logger
from config.settings import TEMP_DIR
from services.multimedia.audio_service import text_to_speech_google, process_audio
from services.multimedia.image_service import get_image_base64

router = APIRouter()

@router.post("/analyze_image")
async def analyze_image_endpoint(
    file: UploadFile = File(...),
    openai_api_key: str = Form(...),
    member_id: Optional[str] = Form(None),
    prompt: Optional[str] = Form("Mô tả chi tiết hình ảnh này bằng tiếng Việt."),
    content_type: str = Form("image")
):
    """Phân tích hình ảnh sử dụng OpenAI Vision."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File tải lên không phải là hình ảnh.")
    if not openai_api_key or "sk-" not in openai_api_key:
         raise HTTPException(status_code=400, detail="OpenAI API key không hợp lệ.")

    try:
        from openai import OpenAI
        from PIL import Image
        from io import BytesIO
        import asyncio
        
        image_content = await file.read()
        img = Image.open(BytesIO(image_content))
        img_base64_url = get_image_base64(img)

        if not img_base64_url:
             raise HTTPException(status_code=500, detail="Không thể xử lý ảnh thành base64.")

        client = OpenAI(api_key=openai_api_key)
        response = await asyncio.to_thread(
             client.chat.completions.create,
             model="gpt-4o-mini",
             messages=[
                 {"role": "system", "content": "Bạn là chuyên gia phân tích hình ảnh. Mô tả chi tiết, nếu là món ăn, nêu tên và gợi ý công thức/nguyên liệu. Nếu là hoạt động, mô tả hoạt động đó."},
                 {"role": "user", "content": [
                     {"type": "text", "text": prompt},
                     {"type": "image_url", "image_url": {"url": img_base64_url}}
                 ]}
             ],
             max_tokens=1000
        )

        analysis_text = response.choices[0].message.content
        audio_response = text_to_speech_google(analysis_text)

        return {
            "analysis": analysis_text,
            "member_id": member_id,
            "content_type": content_type,
            "audio_response": audio_response
        }

    except Exception as e:
        logger.error(f"Lỗi khi phân tích hình ảnh: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lỗi khi phân tích hình ảnh: {str(e)}")

@router.post("/transcribe_audio")
async def transcribe_audio_endpoint(
    file: UploadFile = File(...),
    openai_api_key: str = Form(...)
):
    """Chuyển đổi audio thành text."""
    if not file.content_type.startswith("audio/"):
         logger.warning(f"Content-Type file audio không chuẩn: {file.content_type}. Vẫn thử xử lý.")
    if not openai_api_key or "sk-" not in openai_api_key:
         raise HTTPException(status_code=400, detail="OpenAI API key không hợp lệ.")

    temp_audio_path = os.path.join(TEMP_DIR, f"{uuid.uuid4()}_{file.filename}")
    try:
        from openai import OpenAI
        import asyncio
        import uuid
        
        audio_content = await file.read()
        with open(temp_audio_path, "wb") as f:
            f.write(audio_content)

        client = OpenAI(api_key=openai_api_key)
        with open(temp_audio_path, "rb") as audio_file_obj:
            transcript = await asyncio.to_thread(
                client.audio.transcriptions.create,
                model="whisper-1",
                file=audio_file_obj
            )

        return {"text": transcript.text}

    except Exception as e:
        logger.error(f"Lỗi khi xử lý file audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý file audio: {str(e)}")
    finally:
        if os.path.exists(temp_audio_path):
            try: os.remove(temp_audio_path)
            except OSError: pass


@router.post("/tts")
async def text_to_speech_endpoint(
    text: str = Form(...),
    lang: str = Form(default="vi"),
    slow: bool = Form(default=False)
):
    """Chuyển đổi text thành audio base64 dùng gTTS."""
    try:
        if not text:
            raise HTTPException(status_code=400, detail="Thiếu nội dung văn bản.")

        audio_base64 = text_to_speech_google(text, lang, slow)
        if audio_base64:
            return {
                "audio_data": audio_base64,
                "format": "mp3",
                "lang": lang,
                "provider": "Google TTS"
            }
        else:
            raise HTTPException(status_code=500, detail="Không thể tạo file âm thanh.")
    except Exception as e:
        logger.error(f"Lỗi trong text_to_speech_endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý TTS: {str(e)}")