from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional

from config.logging_config import logger
from config.settings import OPENWEATHERMAP_API_KEY
from services.weather.weather_service import WeatherService

router = APIRouter()

@router.get("/weather")
async def get_weather(
    location: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    type: str = "current",  # "current" hoặc "forecast"
    lang: str = "vi"
):
    """Lấy thông tin thời tiết từ OpenWeatherMap."""
    api_key = OPENWEATHERMAP_API_KEY
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenWeatherMap API key không có sẵn")
        
    weather_service = WeatherService(api_key)
    
    # Ưu tiên địa điểm, sau đó đến tọa độ
    if location:
        logger.info(f"API call: Sử dụng địa điểm: {location}")
        if type == "current":
            result = await weather_service.get_current_weather(location=location, lang=lang)
        else:
            result = await weather_service.get_forecast(location=location, lang=lang)
    elif lat is not None and lon is not None:
        logger.info(f"API call: Sử dụng tọa độ: lat={lat}, lon={lon}")
        if type == "current":
            result = await weather_service.get_current_weather(lat=lat, lon=lon, lang=lang)
        else:
            result = await weather_service.get_forecast(lat=lat, lon=lon, lang=lang)
    else:
        logger.info("API call: Không có địa điểm/tọa độ, sử dụng mặc định Hà Nội")
        if type == "current":
            result = await weather_service.get_current_weather(location="Hanoi", lang=lang)
        else:
            result = await weather_service.get_forecast(location="Hanoi", lang=lang)
        
    if not result:
        raise HTTPException(status_code=500, detail="Không thể lấy dữ liệu thời tiết")
        
    return result