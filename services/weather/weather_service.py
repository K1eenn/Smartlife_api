from __future__ import annotations

import asyncio
import datetime
import requests
from typing import Dict, Any, Optional, List

from config.logging_config import logger

class WeatherService:
    """Dịch vụ lấy dữ liệu thời tiết từ OpenWeatherMap API."""
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.openweathermap.org/data/2.5"
        
    async def get_current_weather(self, lat=None, lon=None, location=None, lang="vi"):
        """
        Lấy thông tin thời tiết hiện tại. Ưu tiên sử dụng tọa độ (lat/lon) nếu có,
        nếu không thì dùng location để tìm kiếm.
        """
        try:
            if lat is not None and lon is not None:
                # Sử dụng tọa độ
                url = f"{self.base_url}/weather"
                params = {
                    "lat": lat,
                    "lon": lon,
                    "appid": self.api_key,
                    "units": "metric",
                    "lang": lang
                }
            elif location:
                # Sử dụng tên địa điểm
                url = f"{self.base_url}/weather"
                params = {
                    "q": location,
                    "appid": self.api_key,
                    "units": "metric",
                    "lang": lang
                }
            else:
                # Mặc định là Hà Nội
                url = f"{self.base_url}/weather"
                params = {
                    "q": "Hanoi,vn",
                    "appid": self.api_key,
                    "units": "metric",
                    "lang": lang
                }
                
            response = await asyncio.to_thread(
                requests.get, url, params=params, timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"OpenWeatherMap API error: {response.status_code} - {response.text}")
                return None
                
            data = response.json()
            return self._process_current_weather(data)
            
        except Exception as e:
            logger.error(f"Error fetching weather data: {e}", exc_info=True)
            return None
            
    async def get_forecast(self, lat=None, lon=None, location=None, lang="vi", days=5):
        """
        Lấy dự báo thời tiết cho nhiều ngày. Ưu tiên sử dụng tọa độ (lat/lon) nếu có,
        nếu không thì dùng location để tìm kiếm.
        """
        try:
            if lat is not None and lon is not None:
                # Sử dụng tọa độ
                url = f"{self.base_url}/forecast"
                params = {
                    "lat": lat,
                    "lon": lon,
                    "appid": self.api_key,
                    "units": "metric",
                    "lang": lang,
                    "cnt": days * 8  # API trả về dữ liệu 3 giờ một lần, 8 lần/ngày
                }
            elif location:
                # Sử dụng tên địa điểm
                url = f"{self.base_url}/forecast"
                params = {
                    "q": location,
                    "appid": self.api_key,
                    "units": "metric",
                    "lang": lang,
                    "cnt": days * 8
                }
            else:
                # Mặc định là Hà Nội
                url = f"{self.base_url}/forecast"
                params = {
                    "q": "Hanoi,vn",
                    "appid": self.api_key,
                    "units": "metric",
                    "lang": lang,
                    "cnt": days * 8
                }
                
            response = await asyncio.to_thread(
                requests.get, url, params=params, timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"OpenWeatherMap API error: {response.status_code} - {response.text}")
                return None
                
            data = response.json()
            return self._process_forecast(data)
            
        except Exception as e:
            logger.error(f"Error fetching weather forecast: {e}", exc_info=True)
            return None
    
    def _process_current_weather(self, data):
        """Xử lý dữ liệu thời tiết hiện tại thành định dạng dễ sử dụng."""
        try:
            result = {
                "location": {
                    "name": data.get("name", ""),
                    "country": data.get("sys", {}).get("country", ""),
                    "lat": data.get("coord", {}).get("lat"),
                    "lon": data.get("coord", {}).get("lon"),
                },
                "current": {
                    "dt": data.get("dt"),
                    "date": datetime.datetime.fromtimestamp(data.get("dt", 0)),
                    "temp": data.get("main", {}).get("temp"),
                    "feels_like": data.get("main", {}).get("feels_like"),
                    "temp_min": data.get("main", {}).get("temp_min"),
                    "temp_max": data.get("main", {}).get("temp_max"),
                    "humidity": data.get("main", {}).get("humidity"),
                    "pressure": data.get("main", {}).get("pressure"),
                    "weather": {
                        "id": data.get("weather", [{}])[0].get("id"),
                        "main": data.get("weather", [{}])[0].get("main"),
                        "description": data.get("weather", [{}])[0].get("description"),
                        "icon": data.get("weather", [{}])[0].get("icon"),
                    },
                    "wind": {
                        "speed": data.get("wind", {}).get("speed"),
                        "deg": data.get("wind", {}).get("deg"),
                    },
                    "clouds": data.get("clouds", {}).get("all"),
                    "visibility": data.get("visibility"),
                    "sunrise": datetime.datetime.fromtimestamp(data.get("sys", {}).get("sunrise", 0)),
                    "sunset": datetime.datetime.fromtimestamp(data.get("sys", {}).get("sunset", 0)),
                }
            }
            
            # Thêm đường dẫn đến icon
            if result["current"]["weather"]["icon"]:
                result["current"]["weather"]["icon_url"] = f"https://openweathermap.org/img/wn/{result['current']['weather']['icon']}@2x.png"
            
            return result
        except Exception as e:
            logger.error(f"Error processing weather data: {e}", exc_info=True)
            return None
    
    def _process_forecast(self, data):
        """Xử lý dữ liệu dự báo thời tiết thành định dạng dễ sử dụng."""
        try:
            result = {
                "location": {
                    "name": data.get("city", {}).get("name", ""),
                    "country": data.get("city", {}).get("country", ""),
                    "lat": data.get("city", {}).get("coord", {}).get("lat"),
                    "lon": data.get("city", {}).get("coord", {}).get("lon"),
                },
                "forecast": []
            }
            
            # Nhóm dự báo theo ngày
            forecasts_by_day = {}
            
            for item in data.get("list", []):
                dt = datetime.datetime.fromtimestamp(item.get("dt", 0))
                day_key = dt.strftime("%Y-%m-%d")
                
                if day_key not in forecasts_by_day:
                    forecasts_by_day[day_key] = []
                
                forecast_item = {
                    "dt": item.get("dt"),
                    "date": dt,
                    "time": dt.strftime("%H:%M"),
                    "temp": item.get("main", {}).get("temp"),
                    "feels_like": item.get("main", {}).get("feels_like"),
                    "temp_min": item.get("main", {}).get("temp_min"),
                    "temp_max": item.get("main", {}).get("temp_max"),
                    "humidity": item.get("main", {}).get("humidity"),
                    "weather": {
                        "id": item.get("weather", [{}])[0].get("id"),
                        "main": item.get("weather", [{}])[0].get("main"),
                        "description": item.get("weather", [{}])[0].get("description"),
                        "icon": item.get("weather", [{}])[0].get("icon"),
                    },
                    "wind": {
                        "speed": item.get("wind", {}).get("speed"),
                        "deg": item.get("wind", {}).get("deg"),
                    },
                    "clouds": item.get("clouds", {}).get("all"),
                    "pop": item.get("pop", 0) * 100,  # Chuyển xác suất mưa từ 0-1 thành phần trăm
                }
                
                # Thêm đường dẫn đến icon
                if forecast_item["weather"]["icon"]:
                    forecast_item["weather"]["icon_url"] = f"https://openweathermap.org/img/wn/{forecast_item['weather']['icon']}@2x.png"
                
                forecasts_by_day[day_key].append(forecast_item)
            
            # Tổng hợp dữ liệu theo ngày
            for day_key, items in forecasts_by_day.items():
                day_summary = {
                    "date": day_key,
                    "day_of_week": datetime.datetime.strptime(day_key, "%Y-%m-%d").strftime("%A"),
                    "temp_min": min(item["temp_min"] for item in items if "temp_min" in item),
                    "temp_max": max(item["temp_max"] for item in items if "temp_max" in item),
                    "hourly": sorted(items, key=lambda x: x["date"]),
                    "main_weather": self._get_main_weather_for_day(items),
                }
                result["forecast"].append(day_summary)
            
            # Sắp xếp dự báo theo ngày
            result["forecast"] = sorted(result["forecast"], key=lambda x: x["date"])
            
            return result
        except Exception as e:
            logger.error(f"Error processing forecast data: {e}", exc_info=True)
            return None
    
    def _get_main_weather_for_day(self, hourly_items):
        """Xác định thời tiết chính trong ngày dựa trên các dự báo theo giờ."""
        # Ưu tiên thời tiết buổi sáng và chiều (9h-18h)
        daytime_items = [item for item in hourly_items 
                        if 9 <= item["date"].hour < 18]
        
        if not daytime_items:
            daytime_items = hourly_items
            
        # Đếm tần suất xuất hiện của mỗi loại thời tiết
        weather_counts = {}
        for item in daytime_items:
            weather_id = item["weather"]["id"]
            weather_counts[weather_id] = weather_counts.get(weather_id, 0) + 1
            
        # Lấy loại thời tiết xuất hiện nhiều nhất
        if weather_counts:
            most_common_weather_id = max(weather_counts.items(), key=lambda x: x[1])[0]
            
            # Tìm item có weather id này
            for item in daytime_items:
                if item["weather"]["id"] == most_common_weather_id:
                    return item["weather"]
        
        # Nếu không tìm được, trả về thời tiết của item đầu tiên
        if daytime_items:
            return daytime_items[0]["weather"]
            
        return {
            "id": 800,
            "main": "Clear",
            "description": "trời quang đãng",
            "icon": "01d",
            "icon_url": "https://openweathermap.org/img/wn/01d@2x.png"
        }

def format_weather_for_prompt(weather_data, forecast_data=None):
    """
    Định dạng dữ liệu thời tiết thành text để đưa vào prompt.
    
    Args:
        weather_data: Dữ liệu thời tiết hiện tại
        forecast_data: Dữ liệu dự báo thời tiết
        
    Returns:
        Chuỗi thông tin thời tiết
    """
    result = []
    
    # Kiểm tra xem weather_data có dữ liệu không
    if not weather_data:
        return "Không có thông tin thời tiết."
        
    # Lấy thông tin địa điểm
    location_name = weather_data.get("location", {}).get("name", "")
    country = weather_data.get("location", {}).get("country", "")
    
    # Đảm bảo luôn có thông tin địa điểm
    if not location_name:
        location_name = "Hà Nội"
        country = "VN"
        
    location_str = f"{location_name}, {country}" if country else location_name
    
    # Thời tiết hiện tại
    current = weather_data.get("current", {})
    if current:
        temp = current.get("temp")
        feels_like = current.get("feels_like")
        humidity = current.get("humidity")
        weather_desc = current.get("weather", {}).get("description", "")
        wind_speed = current.get("wind", {}).get("speed")
        
        current_date_str = current.get("date").strftime("%d/%m/%Y %H:%M") if isinstance(current.get("date"), datetime.datetime) else "hiện tại"
        
        result.append(f"Thời tiết hiện tại tại {location_str} ({current_date_str}):")
        if temp is not None:
            result.append(f"- Nhiệt độ: {temp}°C (cảm giác như {feels_like}°C)")
        if weather_desc:
            result.append(f"- Thời tiết: {weather_desc}")
        if humidity is not None:
            result.append(f"- Độ ẩm: {humidity}%")
        if wind_speed is not None:
            result.append(f"- Gió: {wind_speed} m/s")
            
    # Dự báo thời tiết
    if forecast_data and forecast_data.get("forecast"):
        result.append("\nDự báo thời tiết:")
        
        # Chỉ hiển thị 3 ngày đầu tiên
        for i, day in enumerate(forecast_data.get("forecast", [])[:3]):
            date_str = day.get("date", "")
            day_of_week = datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%A") if date_str else ""
            
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
            
            formatted_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y") if date_str else ""
            weather_desc = day.get("main_weather", {}).get("description", "")
            temp_min = day.get("temp_min")
            temp_max = day.get("temp_max")
            
            result.append(f"\n- {day_of_week_vi}, {formatted_date}:")
            result.append(f"  Thời tiết: {weather_desc}")
            result.append(f"  Nhiệt độ: {temp_min}°C đến {temp_max}°C")
    
    # Thêm ghi chú
    result.append(f"\n(Dữ liệu thời tiết cho khu vực: {location_str})")
    
    return "\n".join(result)