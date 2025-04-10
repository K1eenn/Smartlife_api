from __future__ import annotations

import re
import json
import asyncio
import datetime
from typing import Dict, Any, Optional, List, Tuple

from config.logging_config import logger
from core.datetime_handler import DateTimeHandler
from services.weather.weather_service import WeatherService

class WeatherQueryParser:
    """
    Phân tích truy vấn thời tiết để trích xuất địa điểm và thời gian.
    Sử dụng DateTimeHandler để tính toán ngày cụ thể từ mô tả tương đối.
    """
    
    @classmethod
    async def parse_weather_query(cls, query: str, openai_api_key: str) -> Tuple[bool, str, Optional[str]]:
        """
        Phân tích truy vấn thời tiết để xác định:
        - Có phải truy vấn thời tiết không
        - Địa điểm nào
        - Thời gian nào (nếu có)
        
        Args:
            query: Chuỗi truy vấn của người dùng 
            openai_api_key: API key của OpenAI
            
        Returns:
            Tuple (is_weather_query, location, date_description)
        """
        if not query or not openai_api_key:
            return False, None, None
            
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_api_key)
            
            system_prompt = """
Bạn là một hệ thống phân loại truy vấn thời tiết thông minh. Nhiệm vụ của bạn là:
1. Xác định xem câu hỏi có phải là về thời tiết hoặc liên quan đến thời tiết không (`is_weather_query`).
2. Nếu là truy vấn thời tiết, xác định địa điểm đề cập trong câu hỏi (`location`).
   - Trích xuất TÊN ĐỊA ĐIỂM CHÍNH XÁC từ câu hỏi, ví dụ: "Hà Nội", "Đà Nẵng", "Sài Gòn", "Ho Chi Minh City"
   - Chỉ trả về "Hanoi" khi câu hỏi KHÔNG đề cập đến bất kỳ địa điểm nào cụ thể.
   - Đối với "Sài Gòn", hãy trả về "Ho Chi Minh City" để API tìm kiếm chính xác.
3. Nếu là truy vấn thời tiết, phân tích xem câu hỏi có đề cập đến thời gian cụ thể không (`date_description`).
   - Trích xuất MÔ TẢ THỜI GIAN NGUYÊN BẢN từ câu hỏi, ví dụ: "ngày mai", "thứ 2 tuần sau", "cuối tuần"
   - Trả về null nếu không có mô tả thời gian nào được đề cập (tức là hỏi về thời tiết hiện tại)
   - QUAN TRỌNG: Đừng cố diễn giải hay chuyển đổi mô tả thời gian, chỉ trích xuất đúng nguyên từ mô tả.

Ví dụ:
- User: "thời tiết ở Đà Nẵng hôm nay" -> { "is_weather_query": true, "location": "Da Nang", "date_description": "hôm nay" }
- User: "thời tiết Hà Nội thứ 2 tuần sau" -> { "is_weather_query": true, "location": "Hanoi", "date_description": "thứ 2 tuần sau" }
- User: "trời có mưa không" -> { "is_weather_query": true, "location": "Hanoi", "date_description": null }
- User: "dự báo thời tiết cuối tuần Sài Gòn" -> { "is_weather_query": true, "location": "Ho Chi Minh City", "date_description": "cuối tuần" }
- User: "kết quả trận MU tối qua" -> { "is_weather_query": false, "location": null, "date_description": null }

Trả lời DƯỚI DẠNG JSON HỢP LỆ với 3 trường: is_weather_query (boolean), location (string hoặc null), date_description (string hoặc null).
"""
            response = await asyncio.to_thread(
                 client.chat.completions.create,
                 model="gpt-4o-mini",
                 messages=[
                     {"role": "system", "content": system_prompt},
                     {"role": "user", "content": f"Câu hỏi của người dùng: \"{query}\""}
                 ],
                 temperature=0.1,
                 max_tokens=150,
                 response_format={"type": "json_object"}
            )

            result_str = response.choices[0].message.content
            logger.info(f"Kết quả parse_weather_query (raw): {result_str}")

            try:
                result = json.loads(result_str)
                is_weather_query = result.get("is_weather_query", False)
                location = result.get("location")
                date_description = result.get("date_description")
                
                if is_weather_query and not location:
                    location = "Hanoi"  # Mặc định là Hà Nội
                    
                logger.info(f"Phân tích truy vấn '{query}': is_weather_query={is_weather_query}, location='{location}', date_description='{date_description}'")
                return is_weather_query, location, date_description

            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"Lỗi giải mã JSON từ parse_weather_query: {e}. Raw: {result_str}")
                return False, None, None
                
        except Exception as e:
            logger.error(f"Lỗi khi gọi OpenAI trong parse_weather_query: {e}", exc_info=True)
            return False, None, None

    @classmethod
    async def get_forecast_for_specific_date(cls, weather_service, location: str, date_description: str, 
                                       lat: Optional[float] = None, lon: Optional[float] = None,
                                       days: int = 7, lang: str = "vi"):
        """
        Lấy dự báo thời tiết cho ngày cụ thể dựa trên mô tả ngày.
        """
        # Đảm bảo luôn có location
        if not location:
            location = "Hanoi"
            
        # Sử dụng DateTimeHandler để phân tích mô tả ngày
        try:
            target_date = DateTimeHandler.parse_date(date_description)
            if not target_date:
                logger.warning(f"Không thể phân tích mô tả ngày '{date_description}', sử dụng ngày hiện tại")
                target_date = datetime.date.today()
                
            # Format lại ngày để hiển thị
            date_text = target_date.strftime("%d/%m/%Y")
            
            # Tính số ngày cần dự báo (từ hôm nay đến target_date)
            today = datetime.date.today()
            days_diff = (target_date - today).days
            
            # Đảm bảo dự báo đủ số ngày
            forecast_days = max(days_diff + 1, 1)
            if forecast_days > 7:  # OpenWeatherMap giới hạn 7 ngày
                logger.warning(f"Ngày yêu cầu quá xa trong tương lai ({days_diff} ngày), dự báo có thể không chính xác")
                forecast_days = 7
                
            logger.info(f"Lấy dự báo thời tiết cho '{location}', mục tiêu ngày: {date_text} (sau {days_diff} ngày)")
                
            # Lấy dữ liệu thời tiết hiện tại
            if lat is not None and lon is not None:
                current_weather = await weather_service.get_current_weather(lat=lat, lon=lon, lang=lang)
                forecast = await weather_service.get_forecast(lat=lat, lon=lon, lang=lang, days=forecast_days)
            else:
                current_weather = await weather_service.get_current_weather(location=location, lang=lang)
                forecast = await weather_service.get_forecast(location=location, lang=lang, days=forecast_days)
                
            return current_weather, forecast, target_date, date_text
                
        except Exception as e:
            logger.error(f"Lỗi khi lấy dự báo cho ngày cụ thể: {e}", exc_info=True)
            return None, None, None, None
    
    @classmethod
    def format_weather_for_date(cls, current_weather, forecast, target_date, date_text=None):
        """
        Định dạng thông tin thời tiết cho ngày cụ thể để đưa vào prompt.
        """
        if not current_weather or not forecast:
            return "Không có thông tin thời tiết."
            
        location_name = current_weather.get("location", {}).get("name", "")
        country = current_weather.get("location", {}).get("country", "")
        
        # Đảm bảo luôn có thông tin địa điểm, mặc định là Hà Nội nếu không có
        if not location_name:
            location_name = "Hà Nội"
            country = "VN"
            
        location_str = f"{location_name}, {country}" if country else location_name
        
        if not date_text and target_date:
            date_text = target_date.strftime("%d/%m/%Y")
        elif not date_text:
            date_text = "ngày được yêu cầu"
            
        target_date_str = target_date.strftime("%Y-%m-%d") if target_date else None
        
        # Nếu ngày mục tiêu là hôm nay, sử dụng thông tin hiện tại
        today = datetime.date.today()
        if target_date == today:
            current = current_weather.get("current", {})
            temp = current.get("temp")
            feels_like = current.get("feels_like")
            humidity = current.get("humidity")
            weather_desc = current.get("weather", {}).get("description", "")
            wind_speed = current.get("wind", {}).get("speed")
            
            sunrise = current.get("sunrise")
            sunset = current.get("sunset")
            sunrise_str = sunrise.strftime("%H:%M") if sunrise else "N/A"
            sunset_str = sunset.strftime("%H:%M") if sunset else "N/A"
            
            result = f"""
    Thông tin thời tiết cho {location_str} vào {date_text} (hôm nay):
    - Nhiệt độ hiện tại: {temp}°C (cảm giác như: {feels_like}°C)
    - Thời tiết: {weather_desc}
    - Độ ẩm: {humidity}%
    - Gió: {wind_speed} m/s
    - Mặt trời mọc: {sunrise_str}, mặt trời lặn: {sunset_str}
    """
        else:
            # Tìm dự báo cho ngày mục tiêu
            target_forecast = None
            for day_forecast in forecast.get("forecast", []):
                if day_forecast.get("date") == target_date_str:
                    target_forecast = day_forecast
                    break
                    
            if target_forecast:
                temp_min = target_forecast.get("temp_min", "N/A")
                temp_max = target_forecast.get("temp_max", "N/A")
                weather_desc = target_forecast.get("main_weather", {}).get("description", "không rõ")
                
                day_of_week = target_date.strftime("%A")
                # Chuyển đổi sang tiếng Việt
                day_of_week_vi = {
                    "Monday": "Thứ Hai",
                    "Tuesday": "Thứ Ba",
                    "Wednesday": "Thứ Tư",
                    "Thursday": "Thứ Năm",
                    "Friday": "Thứ Sáu",
                    "Saturday": "Thứ Bảy",
                    "Sunday": "Chủ Nhật"
                }.get(day_of_week, day_of_week)
                
                result = f"""
    Dự báo thời tiết cho {location_str} vào {date_text} ({day_of_week_vi}):
    - Nhiệt độ: {temp_min}°C đến {temp_max}°C
    - Thời tiết: {weather_desc}
    """
                
                # Thêm thông tin chi tiết theo giờ nếu có
                hourly_data = target_forecast.get("hourly", [])
                if hourly_data:
                    result += "\nDự báo chi tiết theo giờ:\n"
                    
                    # Chỉ hiển thị 4 khung giờ quan trọng
                    key_hours = [8, 12, 16, 20]  # sáng, trưa, chiều, tối
                    key_forecasts = []
                    
                    for hour in key_hours:
                        closest_forecast = min(hourly_data, 
                                            key=lambda x: abs(x.get("date").hour - hour) 
                                            if isinstance(x.get("date"), datetime.datetime) else float('inf'))
                        
                        if isinstance(closest_forecast.get("date"), datetime.datetime):
                            time_str = closest_forecast.get("date").strftime("%H:%M")
                            temp = closest_forecast.get("temp", "N/A")
                            desc = closest_forecast.get("weather", {}).get("description", "không rõ")
                            
                            time_of_day = ""
                            if 6 <= closest_forecast.get("date").hour < 12:
                                time_of_day = "Sáng"
                            elif 12 <= closest_forecast.get("date").hour < 14:
                                time_of_day = "Trưa"
                            elif 14 <= closest_forecast.get("date").hour < 18:
                                time_of_day = "Chiều"
                            else:
                                time_of_day = "Tối"
                                
                            key_forecasts.append(f"- {time_of_day} ({time_str}): {temp}°C, {desc}")
                    
                    result += "\n".join(key_forecasts)
            else:
                result = f"""
    Dự báo thời tiết cho {location_str} vào {date_text}:
    - Không có dữ liệu dự báo chi tiết cho ngày này (có thể ngày này quá xa trong tương lai).
    """
                
                # Thêm dự báo 3 ngày gần nhất
                result += "\nDự báo 3 ngày tới:\n"
                for i, day in enumerate(forecast.get("forecast", [])[:3]):
                    date_obj = datetime.datetime.strptime(day.get("date", ""), "%Y-%m-%d") if day.get("date") else None
                    if date_obj:
                        date_str = date_obj.strftime("%d/%m/%Y")
                        day_name = date_obj.strftime("%A")
                        day_name_vi = {
                            "Monday": "Thứ Hai",
                            "Tuesday": "Thứ Ba",
                            "Wednesday": "Thứ Tư",
                            "Thursday": "Thứ Năm",
                            "Friday": "Thứ Sáu",
                            "Saturday": "Thứ Bảy",
                            "Sunday": "Chủ Nhật"
                        }.get(day_name, day_name)
                        
                        weather_desc = day.get("main_weather", {}).get("description", "không rõ")
                        temp_min = day.get("temp_min", "N/A")
                        temp_max = day.get("temp_max", "N/A")
                        
                        result += f"- {day_name_vi}, {date_str}: {weather_desc}, {temp_min}°C đến {temp_max}°C\n"
        
        # Thêm nhắc nhở về địa điểm
        result += f"\n(Dự báo thời tiết cho khu vực: {location_str})"
        
        return result