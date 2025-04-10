from __future__ import annotations

import base64
from io import BytesIO
from typing import Optional
from PIL import Image

from config.logging_config import logger

def get_image_base64(image_raw: Image.Image) -> Optional[str]:
    """Chuyển đối tượng PIL Image sang base64 data URL."""
    try:
        buffered = BytesIO()
        img_format = image_raw.format if image_raw.format else "JPEG"
        if img_format not in ["JPEG", "PNG", "GIF", "WEBP"]:
             logger.warning(f"Định dạng ảnh không được hỗ trợ trực tiếp '{img_format}', chuyển đổi sang JPEG.")
             img_format = "JPEG"
             if image_raw.mode != "RGB":
                 image_raw = image_raw.convert("RGB")

        image_raw.save(buffered, format=img_format)
        img_byte = buffered.getvalue()
        mime_type = f"image/{img_format.lower()}"
        base64_str = base64.b64encode(img_byte).decode('utf-8')
        return f"data:{mime_type};base64,{base64_str}"
    except Exception as e:
         logger.error(f"Lỗi chuyển đổi ảnh sang base64: {e}", exc_info=True)
         return None