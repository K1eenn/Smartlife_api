from __future__ import annotations

import re
import datetime
from typing import Dict, Any, Optional, List

from config.logging_config import logger

class WeatherAdvisor:
    """
    Lớp cung cấp tư vấn thông minh dựa trên dữ liệu thời tiết.
    Bao gồm tư vấn trang phục, đồ mang theo, địa điểm đi chơi và các gợi ý khác.
    """
    
    # Mức nhiệt độ và phân loại
    TEMP_RANGES = {
        "rất_lạnh": (float('-inf'), 10),  # Dưới 10°C
        "lạnh": (10, 18),                  # 10-18°C
        "mát_mẻ": (18, 22),                # 18-22°C
        "dễ_chịu": (22, 27),               # 22-27°C
        "ấm": (27, 32),                    # 27-32°C
        "nóng": (32, 36),                  # 32-36°C
        "rất_nóng": (36, float('inf'))     # Trên 36°C
    }
    
    # Phân loại thời tiết theo điều kiện
    WEATHER_CONDITIONS = {
        # Mưa
        "mưa_nhẹ": ["mưa nhẹ", "mưa phùn", "mưa rào nhẹ"],
        "mưa_vừa": ["mưa vừa", "mưa rào"],
        "mưa_to": ["mưa to", "mưa lớn", "mưa rào mạnh", "dông", "giông", "mưa rào và dông", "mưa rào và giông"],
        
        # Nắng
        "nắng_nhẹ": ["nắng nhẹ", "trời quang", "quang đãng", "nắng ít"],
        "nắng": ["nắng", "trời nắng", "nắng vừa"],
        "nắng_gắt": ["nắng gắt", "nắng nóng", "nắng gay gắt", "nắng to"],
        
        # Mây
        "có_mây": ["có mây", "trời nhiều mây", "mây thưa", "mây rải rác"],
        "u_ám": ["u ám", "trời âm u", "âm u", "mây đen", "mây đặc"],
        
        # Sương mù
        "sương_mù": ["sương mù", "trời sương mù", "sương", "mù sương"],
        
        # Khác
        "ẩm_ướt": ["ẩm ướt", "độ ẩm cao", "ẩm thấp"],
        "hanh_khô": ["hanh khô", "khô", "khô hanh", "hanh", "khô ráo"],
        "gió_mạnh": ["gió mạnh", "gió lớn", "gió to", "gió cấp", "gió giật"],
    }
    
    # Tư vấn trang phục theo nhiệt độ và điều kiện thời tiết
    CLOTHING_ADVICE = {
        "rất_lạnh": {
            "default": [
                "Áo khoác dày hoặc áo phao",
                "Khăn quàng cổ, găng tay và mũ len",
                "Quần dài dày hoặc quần nỉ",
                "Tất dày và giày bốt hoặc giày kín",
                "Có thể mặc nhiều lớp áo bên trong"
            ],
            "mưa_nhẹ": [
                "Áo khoác dày chống thấm nước",
                "Ủng cao su hoặc giày không thấm nước",
                "Mũ chống mưa hoặc mũ có phủ chống thấm"
            ],
            "mưa_vừa": [
                "Áo mưa hoặc áo khoác chống thấm dày",
                "Ủng cao su cao cổ",
                "Tránh đồ len có thể thấm nước nhiều"
            ],
            "mưa_to": [
                "Áo mưa kín hoặc áo khoác chống thấm nước tốt",
                "Mũ có vành rộng chống nước",
                "Giày và tất dự phòng để thay"
            ]
        },
        "lạnh": {
            "default": [
                "Áo khoác nhẹ hoặc áo len dày",
                "Khăn quàng cổ mỏng",
                "Quần dài",
                "Giày kín"
            ],
            "mưa_nhẹ": [
                "Áo khoác nhẹ chống nước",
                "Mũ chống mưa",
                "Giày kín không thấm nước"
            ],
            "mưa_vừa": [
                "Áo khoác chống thấm",
                "Ủng hoặc giày không thấm nước",
                "Mũ chống mưa"
            ]
        },
        "mát_mẻ": {
            "default": [
                "Áo sơ mi dài tay hoặc áo thun dài tay",
                "Áo khoác mỏng có thể mặc khi trời mát",
                "Quần dài vải nhẹ",
                "Giày thể thao hoặc giày lười"
            ],
            "nắng": [
                "Mũ nhẹ để che nắng",
                "Kính râm"
            ],
            "có_mây": [
                "Áo khoác mỏng có thể mặc/cởi linh hoạt"
            ]
        },
        "dễ_chịu": {
            "default": [
                "Áo thun hoặc áo sơ mi ngắn tay",
                "Quần dài vải mỏng hoặc quần lửng",
                "Giày mở thoáng hoặc sandal"
            ],
            "nắng": [
                "Mũ rộng vành để che nắng",
                "Kính râm",
                "Khẩu trang chống nắng (nếu ra ngoài lâu)"
            ],
            "mưa_nhẹ": [
                "Áo khoác mỏng chống thấm",
                "Giày không thấm nước"
            ]
        },
        "ấm": {
            "default": [
                "Áo thun thoáng mát",
                "Váy hoặc quần short (nếu đi chơi)",
                "Quần vải nhẹ thoáng khí",
                "Sandal hoặc dép"
            ],
            "nắng": [
                "Mũ rộng vành",
                "Kính râm",
                "Khẩu trang chống nắng",
                "Áo chống nắng nhẹ (nếu ra ngoài lâu)"
            ],
            "mưa_nhẹ": [
                "Áo mưa mỏng có thể gấp gọn mang theo"
            ]
        },
        "nóng": {
            "default": [
                "Áo thun mỏng nhẹ, thoáng khí",
                "Quần short hoặc váy ngắn thoáng mát",
                "Dép hoặc sandal thoáng",
                "Tránh quần áo tối màu hấp thụ nhiệt"
            ],
            "nắng": [
                "Áo chống nắng nhẹ, thoáng khí",
                "Mũ rộng vành",
                "Kính râm chống tia UV",
                "Khẩu trang chống nắng"
            ]
        },
        "rất_nóng": {
            "default": [
                "Áo thun siêu nhẹ, áo ba lỗ hoặc áo sát nách",
                "Quần đùi hoặc váy siêu ngắn, thoáng mát nhất có thể",
                "Dép lê hoặc sandal mỏng",
                "Mặc đồ sáng màu phản chiếu nhiệt"
            ],
            "nắng_gắt": [
                "Áo chống nắng UPF 50+ nếu phải ra ngoài",
                "Mũ rộng vành kín",
                "Kính râm chống UV cao",
                "Khẩu trang chống nắng"
            ]
        }
    }
    
    # Tư vấn đồ mang theo dựa vào điều kiện thời tiết
    ITEMS_TO_BRING = {
        "mưa_nhẹ": [
            "Ô nhỏ gấp gọn",
            "Áo mưa mỏng hoặc áo khoác chống thấm"
        ],
        "mưa_vừa": [
            "Ô chắc chắn",
            "Áo mưa",
            "Túi chống nước cho điện thoại và ví"
        ],
        "mưa_to": [
            "Áo mưa kín",
            "Ủng cao su nếu phải đi bộ nhiều",
            "Túi chống nước cho đồ điện tử",
            "Quần áo dự phòng (nếu đi xa)"
        ],
        "nắng": [
            "Kem chống nắng SPF 30+",
            "Kính râm",
            "Mũ",
            "Nước uống"
        ],
        "nắng_gắt": [
            "Kem chống nắng SPF 50+",
            "Kính râm chống UV",
            "Mũ rộng vành",
            "Khăn che cổ",
            "Nhiều nước uống",
            "Dù che nắng",
            "Quạt cầm tay hoặc quạt mini"
        ],
        "rất_lạnh": [
            "Găng tay",
            "Mũ len",
            "Khăn quàng cổ",
            "Miếng dán giữ nhiệt",
            "Đồ uống giữ nhiệt"
        ],
        "hanh_khô": [
            "Xịt khoáng hoặc bình phun sương",
            "Kem dưỡng ẩm",
            "Son dưỡng môi",
            "Nhiều nước uống"
        ],
        "gió_mạnh": [
            "Mũ có dây buộc",
            "Áo khoác chắn gió",
            "Kính bảo vệ mắt khỏi bụi"
        ],
        "sương_mù": [
            "Đèn pin hoặc đèn đeo trán",
            "Khẩu trang",
            "Khăn lau kính"
        ]
    }
    
    # Tư vấn địa điểm đi chơi theo thời tiết
    PLACES_TO_GO = {
        "đẹp_trời": [
            "Công viên",
            "Vườn bách thảo",
            "Hồ",
            "Đi picnic",
            "Các điểm tham quan ngoài trời",
            "Đạp xe quanh hồ",
            "Đồi núi (nếu có)",
            "Bãi biển (nếu có)"
        ],
        "mưa": [
            "Trung tâm thương mại",
            "Bảo tàng",
            "Rạp chiếu phim",
            "Quán cà phê",
            "Nhà sách",
            "Trung tâm giải trí trong nhà",
            "Tiệm trà",
            "Nhà hàng ấm cúng"
        ],
        "nóng": [
            "Bể bơi",
            "Rạp chiếu phim có máy lạnh",
            "Trung tâm thương mại có điều hòa",
            "Công viên nước",
            "Quán cà phê có máy lạnh",
            "Bảo tàng có điều hòa",
            "Thư viện"
        ],
        "lạnh": [
            "Quán cà phê ấm cúng",
            "Nhà hàng lẩu",
            "Trung tâm thương mại có hệ thống sưởi",
            "Phòng trà",
            "Nhà hát",
            "Tiệm bánh"
        ]
    }
    
    # Các hoạt động phù hợp với điều kiện thời tiết
    ACTIVITIES = {
        "đẹp_trời": [
            "Đi bộ dạo phố",
            "Đạp xe",
            "Chạy bộ",
            "Picnic",
            "Chụp ảnh ngoài trời",
            "Vẽ tranh phong cảnh",
            "Trồng cây",
            "Câu cá (nếu có địa điểm thích hợp)"
        ],
        "mưa": [
            "Đọc sách",
            "Xem phim",
            "Nấu ăn tại nhà",
            "Chơi board game với gia đình",
            "Học một kỹ năng mới trực tuyến",
            "Sắp xếp lại tủ đồ",
            "Thử một quán cà phê mới"
        ],
        "nóng": [
            "Bơi lội",
            "Uống đồ lạnh tại một quán cà phê",
            "Thưởng thức kem",
            "Ngâm chân trong nước mát",
            "Xem phim trong rạp có điều hòa"
        ],
        "lạnh": [
            "Thưởng thức đồ uống nóng",
            "Ăn lẩu",
            "Nướng BBQ",
            "Xem phim dưới chăn ấm",
            "Nghe nhạc và đọc sách"
        ]
    }

    @classmethod
    def get_temperature_category(cls, temp: float) -> str:
        """
        Xác định danh mục nhiệt độ dựa trên nhiệt độ đầu vào.
        
        Args:
            temp: Nhiệt độ (độ C)
            
        Returns:
            Danh mục nhiệt độ (ví dụ: "lạnh", "dễ_chịu", "nóng"...)
        """
        for category, (min_temp, max_temp) in cls.TEMP_RANGES.items():
            if min_temp <= temp < max_temp:
                return category
        return "dễ_chịu"  # Mặc định nếu không khớp
    
    @classmethod
    def get_weather_conditions(cls, weather_desc: str) -> List[str]:
        """
        Xác định các điều kiện thời tiết dựa trên mô tả.
        
        Args:
            weather_desc: Mô tả thời tiết (ví dụ: "mưa rào và có gió")
            
        Returns:
            Danh sách các điều kiện thời tiết phù hợp
        """
        weather_desc = weather_desc.lower()
        conditions = []
        
        for condition, keywords in cls.WEATHER_CONDITIONS.items():
            if any(keyword in weather_desc for keyword in keywords):
                conditions.append(condition)
                
        # Phân loại chung hơn dựa trên các điều kiện cụ thể
        if any(cond.startswith("mưa_") for cond in conditions):
            conditions.append("mưa")
            
        if any(cond.startswith("nắng_") for cond in conditions):
            conditions.append("nắng")
            
        if not conditions:
            # Nếu không tìm thấy điều kiện cụ thể, đoán theo một số từ khóa chung
            if "mưa" in weather_desc:
                conditions.append("mưa")
            elif "nắng" in weather_desc:
                conditions.append("nắng")
            elif any(word in weather_desc for word in ["quang", "đẹp", "trong"]):
                conditions.append("đẹp_trời")
                
        return conditions if conditions else ["đẹp_trời"]  # Mặc định là trời đẹp nếu không xác định được
    
    @classmethod
    def get_general_weather_category(cls, temp_category: str, weather_conditions: List[str]) -> str:
        """
        Xác định danh mục thời tiết tổng quát cho tư vấn địa điểm và hoạt động.
        
        Args:
            temp_category: Danh mục nhiệt độ
            weather_conditions: Danh sách các điều kiện thời tiết
            
        Returns:
            Danh mục thời tiết tổng quát
        """
        if "mưa" in weather_conditions or any(cond.startswith("mưa_") for cond in weather_conditions):
            return "mưa"
            
        if temp_category in ["nóng", "rất_nóng"] or "nắng_gắt" in weather_conditions:
            return "nóng"
            
        if temp_category in ["lạnh", "rất_lạnh"]:
            return "lạnh"
            
        return "đẹp_trời"
    
    @classmethod
    def analyze_weather_data(cls, weather_data: Dict[str, Any], target_date: Optional[datetime.date] = None) -> Dict[str, Any]:
        """
        Phân tích dữ liệu thời tiết để chuẩn bị cho tư vấn.
        
        Args:
            weather_data: Dữ liệu thời tiết (current_weather hoặc forecast)
            target_date: Ngày cần phân tích (None = ngày hiện tại)
            
        Returns:
            Dict chứa thông tin phân tích
        """
        analysis = {}
        today = datetime.date.today()
        is_current_weather = False
        
        # Xác định nếu dữ liệu là thời tiết hiện tại
        if weather_data.get("current") is not None:
            is_current_weather = True
            
        # Xử lý thời tiết hiện tại
        if is_current_weather and (target_date is None or target_date == today):
            current = weather_data.get("current", {})
            temp = current.get("temp")
            feels_like = current.get("feels_like")
            humidity = current.get("humidity")
            weather_desc = current.get("weather", {}).get("description", "")
            wind_speed = current.get("wind", {}).get("speed")
            
            if temp is not None:
                analysis["temperature"] = temp
                analysis["temp_category"] = cls.get_temperature_category(temp)
            
            if feels_like is not None:
                analysis["feels_like"] = feels_like
                # Sử dụng feels_like để tư vấn trang phục nếu khác biệt nhiều với nhiệt độ thực
                if abs(feels_like - temp) > 3:
                    # Nếu cảm giác lạnh hơn hoặc nóng hơn đáng kể
                    analysis["feels_temp_category"] = cls.get_temperature_category(feels_like)
                    
            if humidity is not None:
                analysis["humidity"] = humidity
                if humidity > 80:
                    analysis["high_humidity"] = True
                elif humidity < 30:
                    analysis["low_humidity"] = True
                    
            if weather_desc:
                analysis["weather_desc"] = weather_desc
                analysis["weather_conditions"] = cls.get_weather_conditions(weather_desc)
                
            if wind_speed is not None:
                analysis["wind_speed"] = wind_speed
                if wind_speed > 8:  # m/s, khoảng 30 km/h
                    analysis["strong_wind"] = True
                    if "gió_mạnh" not in analysis.get("weather_conditions", []):
                        analysis.setdefault("weather_conditions", []).append("gió_mạnh")
                        
        # Xử lý dự báo
        else:
            # Tìm dự báo cho ngày cụ thể
            target_date_str = target_date.strftime("%Y-%m-%d") if target_date else today.strftime("%Y-%m-%d")
            target_forecast = None
            
            for day_forecast in weather_data.get("forecast", []):
                if day_forecast.get("date") == target_date_str:
                    target_forecast = day_forecast
                    break
                    
            if target_forecast:
                temp_min = target_forecast.get("temp_min")
                temp_max = target_forecast.get("temp_max")
                weather_desc = target_forecast.get("main_weather", {}).get("description", "")
                
                # Tính nhiệt độ trung bình cho tư vấn trang phục
                if temp_min is not None and temp_max is not None:
                    avg_temp = (temp_min + temp_max) / 2
                    analysis["temperature"] = avg_temp
                    analysis["temp_category"] = cls.get_temperature_category(avg_temp)
                    analysis["temp_range"] = (temp_min, temp_max)
                    
                if weather_desc:
                    analysis["weather_desc"] = weather_desc
                    analysis["weather_conditions"] = cls.get_weather_conditions(weather_desc)
                    
                # Xác định thời điểm trong ngày cho dự báo chi tiết nếu có
                hourly_data = target_forecast.get("hourly", [])
                if hourly_data:
                    morning = None
                    afternoon = None
                    evening = None
                    
                    for hourly in hourly_data:
                        hour = hourly.get("date").hour if isinstance(hourly.get("date"), datetime.datetime) else -1
                        
                        if 6 <= hour < 12 and not morning:
                            morning = hourly
                        elif 12 <= hour < 18 and not afternoon:
                            afternoon = hourly
                        elif 18 <= hour < 23 and not evening:
                            evening = hourly
                            
                    analysis["time_of_day"] = {
                        "morning": morning,
                        "afternoon": afternoon,
                        "evening": evening
                    }
        
        # Xác định danh mục thời tiết tổng quát
        if "temp_category" in analysis and "weather_conditions" in analysis:
            analysis["general_category"] = cls.get_general_weather_category(
                analysis["temp_category"], 
                analysis["weather_conditions"]
            )
            
        return analysis
    
    @classmethod
    def get_clothing_advice(cls, weather_analysis: Dict[str, Any]) -> List[str]:
        """
        Đưa ra tư vấn trang phục dựa trên phân tích thời tiết.
        
        Args:
            weather_analysis: Kết quả phân tích thời tiết
            
        Returns:
            Danh sách các tư vấn trang phục
        """
        advice = []
        
        # Lấy danh mục nhiệt độ (ưu tiên feels_like nếu có)
        temp_category = weather_analysis.get("feels_temp_category", weather_analysis.get("temp_category"))
        if not temp_category:
            return ["Không có đủ thông tin về nhiệt độ để tư vấn trang phục."]
            
        # Lấy tư vấn cơ bản dựa trên nhiệt độ
        if temp_category in cls.CLOTHING_ADVICE:
            advice.extend(cls.CLOTHING_ADVICE[temp_category]["default"])
            
        # Tư vấn bổ sung dựa trên điều kiện thời tiết
        weather_conditions = weather_analysis.get("weather_conditions", [])
        for condition in weather_conditions:
            if condition in cls.CLOTHING_ADVICE.get(temp_category, {}):
                advice.extend(cls.CLOTHING_ADVICE[temp_category][condition])
                
        # Điều chỉnh theo thời điểm trong ngày
        time_of_day = weather_analysis.get("time_of_day", {})
        temp_range = weather_analysis.get("temp_range")
        
        if temp_range and max(temp_range) - min(temp_range) > 8:
            advice.append("Nhiệt độ dao động lớn trong ngày, nên mặc nhiều lớp để dễ điều chỉnh.")
            
        # Điều chỉnh theo độ ẩm
        if weather_analysis.get("high_humidity"):
            advice.append("Độ ẩm cao, nên mặc vải thoáng khí như cotton hoặc linen để thoải mái hơn.")
            
        if weather_analysis.get("low_humidity"):
            advice.append("Độ ẩm thấp, nên mặc quần áo thoải mái và mang theo dưỡng ẩm.")
            
        # Loại bỏ trùng lặp
        unique_advice = []
        advice_set = set()
        
        for item in advice:
            normalized_item = re.sub(r'\s+', ' ', item.lower().strip())
            if normalized_item not in advice_set:
                advice_set.add(normalized_item)
                unique_advice.append(item)
                
        return unique_advice
    
    @classmethod
    def get_items_to_bring(cls, weather_analysis: Dict[str, Any]) -> List[str]:
        """
        Đưa ra tư vấn đồ vật nên mang theo dựa trên phân tích thời tiết.
        
        Args:
            weather_analysis: Kết quả phân tích thời tiết
            
        Returns:
            Danh sách các đồ vật nên mang theo
        """
        items = []
        items.append("Điện thoại và sạc dự phòng")  # Luôn cần thiết
        items.append("Ví/bóp đựng giấy tờ và tiền")
        
        # Thêm đồ vật dựa trên điều kiện thời tiết
        weather_conditions = weather_analysis.get("weather_conditions", [])
        for condition in weather_conditions:
            if condition in cls.ITEMS_TO_BRING:
                items.extend(cls.ITEMS_TO_BRING[condition])
                
        temp_category = weather_analysis.get("temp_category")
        
        # Thêm đồ vật dựa trên nhiệt độ
        if temp_category in ["nóng", "rất_nóng"]:
            items.append("Chai nước để giữ đủ nước")
            items.append("Khăn lau mồ hôi")
            
        if temp_category in ["lạnh", "rất_lạnh"]:
            items.append("Đồ uống giữ nhiệt")
            
        # Thời gian trong ngày
        time_of_day = weather_analysis.get("time_of_day", {})
        if time_of_day.get("evening"):
            items.append("Đèn pin nhỏ hoặc đèn điện thoại (nếu về muộn)")
            
        # Loại bỏ trùng lặp
        unique_items = []
        items_set = set()
        
        for item in items:
            normalized_item = re.sub(r'\s+', ' ', item.lower().strip())
            if normalized_item not in items_set:
                items_set.add(normalized_item)
                unique_items.append(item)
                
        return unique_items
    
    @classmethod
    def get_places_to_go(cls, weather_analysis: Dict[str, Any]) -> List[str]:
        """
        Đưa ra tư vấn địa điểm đi chơi dựa trên phân tích thời tiết.
        
        Args:
            weather_analysis: Kết quả phân tích thời tiết
            
        Returns:
            Danh sách các địa điểm đề xuất
        """
        places = []
        
        # Sử dụng danh mục thời tiết tổng quát
        general_category = weather_analysis.get("general_category", "đẹp_trời")
        
        if general_category in cls.PLACES_TO_GO:
            places.extend(cls.PLACES_TO_GO[general_category])
            
        # Điều chỉnh theo thời điểm cụ thể
        temp_category = weather_analysis.get("temp_category")
        if temp_category == "rất_nóng" and "mưa" not in general_category:
            # Ưu tiên những nơi có điều hòa/mát mẻ khi quá nóng
            for place in cls.PLACES_TO_GO.get("nóng", []):
                if place not in places:
                    places.append(place)
                    
        if temp_category == "rất_lạnh" and "mưa" not in general_category:
            # Ưu tiên những nơi ấm khi quá lạnh
            for place in cls.PLACES_TO_GO.get("lạnh", []):
                if place not in places:
                    places.append(place)
                    
        return places
    
    @classmethod
    def get_activities(cls, weather_analysis: Dict[str, Any]) -> List[str]:
        """
        Đưa ra tư vấn hoạt động dựa trên phân tích thời tiết.
        
        Args:
            weather_analysis: Kết quả phân tích thời tiết
            
        Returns:
            Danh sách các hoạt động đề xuất
        """
        activities = []
        
        # Sử dụng danh mục thời tiết tổng quát
        general_category = weather_analysis.get("general_category", "đẹp_trời")
        
        if general_category in cls.ACTIVITIES:
            activities.extend(cls.ACTIVITIES[general_category])
            
        return activities
    
    @classmethod
    def combine_advice(cls, weather_data: Dict[str, Any], target_date: Optional[datetime.date] = None, 
                     query_type: str = "general") -> Dict[str, Any]:
        """
        Kết hợp tất cả lời khuyên dựa trên dữ liệu thời tiết và loại truy vấn.
        
        Args:
            weather_data: Dữ liệu thời tiết
            target_date: Ngày mục tiêu (None = ngày hiện tại)
            query_type: Loại truy vấn ("clothing", "items", "places", "activities", "general")
            
        Returns:
            Dict chứa tất cả lời khuyên theo loại truy vấn
        """
        # Phân tích dữ liệu thời tiết
        weather_analysis = cls.analyze_weather_data(weather_data, target_date)
        
        # Kết quả cuối cùng
        result = {
            "weather_summary": {
                "temperature": weather_analysis.get("temperature"),
                "weather_desc": weather_analysis.get("weather_desc"),
                "temp_category": weather_analysis.get("temp_category")
            }
        }
        
        # Thêm tư vấn theo loại truy vấn
        if query_type in ["clothing", "general"]:
            result["clothing_advice"] = cls.get_clothing_advice(weather_analysis)
            
        if query_type in ["items", "general"]:
            result["items_to_bring"] = cls.get_items_to_bring(weather_analysis)
            
        if query_type in ["places", "general"]:
            result["places_to_go"] = cls.get_places_to_go(weather_analysis)
            
        if query_type in ["activities", "general"]:
            result["activities"] = cls.get_activities(weather_analysis)
            
        return result
    
    @classmethod
    def format_advice_for_prompt(cls, advice_data: Dict[str, Any], query_type: str = "general", location: str = None) -> str:
        """
        Định dạng lời khuyên để đưa vào prompt.
        
        Args:
            advice_data: Dữ liệu lời khuyên từ combine_advice
            query_type: Loại truy vấn
            location: Tên địa điểm (mới thêm)
            
        Returns:
            Chuỗi lời khuyên định dạng
        """
        result = []
        
        # Thông tin thời tiết tóm tắt
        weather_summary = advice_data.get("weather_summary", {})
        temp = weather_summary.get("temperature")
        weather_desc = weather_summary.get("weather_desc", "")
        
        # Nếu không có location, sử dụng mặc định là Hà Nội
        if not location:
            location = "Hà Nội"
        
        # Nếu là truy vấn chung, thêm giới thiệu
        if query_type == "general":
            intro = f"Dựa trên dữ liệu thời tiết tại {location}"
            if temp is not None:
                intro += f" (nhiệt độ {temp}°C, {weather_desc})"
            intro += ", đây là một số gợi ý cho bạn:"
            result.append(intro)
            result.append("")  # Dòng trống
            
        # Tư vấn trang phục
        if "clothing_advice" in advice_data:
            if query_type == "clothing":
                result.append(f"### Gợi ý trang phục phù hợp với thời tiết tại {location} ({temp}°C, {weather_desc}):")
            else:
                result.append(f"### Trang phục nên mặc khi ở {location}:")
                
            for item in advice_data["clothing_advice"]:
                result.append(f"- {item}")
                
            result.append("")  # Dòng trống
            
        # Đồ vật nên mang theo
        if "items_to_bring" in advice_data:
            if query_type == "items":
                result.append(f"### Những thứ nên mang theo trong thời tiết tại {location} ({temp}°C, {weather_desc}):")
            else:
                result.append(f"### Đồ vật nên mang theo khi đi ra ngoài tại {location}:")
                
            for item in advice_data["items_to_bring"]:
                result.append(f"- {item}")
                
            result.append("")  # Dòng trống
            
        # Địa điểm đề xuất
        if "places_to_go" in advice_data:
            if query_type == "places":
                result.append(f"### Địa điểm đề xuất trong thời tiết tại {location} ({temp}°C, {weather_desc}):")
            else:
                result.append(f"### Địa điểm phù hợp để đi chơi tại {location}:")
                
            for place in advice_data["places_to_go"][:5]:  # Chỉ hiển thị tối đa 5 địa điểm
                result.append(f"- {place}")
                
            result.append("")  # Dòng trống
            
        # Hoạt động đề xuất
        if "activities" in advice_data:
            if query_type == "activities":
                result.append(f"### Hoạt động phù hợp trong thời tiết tại {location} ({temp}°C, {weather_desc}):")
            else:
                result.append(f"### Hoạt động đề xuất tại {location}:")
                
            for activity in advice_data["activities"][:5]:  # Chỉ hiển thị tối đa 5 hoạt động
                result.append(f"- {activity}")
                
        # Thêm thông tin về nguồn dữ liệu thời tiết
        result.append(f"\n(Thông tin dựa trên dữ liệu thời tiết tại {location})")
        
        return "\n".join(result)
    
    @classmethod
    async def detect_weather_advice_need(cls, query: str, openai_api_key: str) -> Tuple[bool, str, Optional[str]]:
        """
        Phát hiện nhu cầu tư vấn liên quan đến thời tiết từ câu hỏi.
        
        Args:
            query: Câu hỏi của người dùng
            openai_api_key: API key của OpenAI
            
        Returns:
            Tuple (is_advice_query, advice_type, location, date_description)
        """
        if not query or not openai_api_key:
            return False, "general", None, None
            
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_api_key)
            
            system_prompt = """
Bạn là một hệ thống phân loại truy vấn tư vấn thời tiết thông minh. Nhiệm vụ của bạn là:
1. Xác định xem câu hỏi có phải là yêu cầu tư vấn liên quan đến thời tiết không (`is_advice_query`).
2. Nếu là yêu cầu tư vấn, xác định loại tư vấn (`advice_type`):
   - "clothing": Tư vấn về trang phục nên mặc (ví dụ: "nên mặc gì", "mặc quần áo gì")
   - "items": Tư vấn về đồ vật nên mang theo (ví dụ: "mang theo gì", "chuẩn bị những gì")
   - "places": Tư vấn về địa điểm đi chơi (ví dụ: "nên đi đâu", "chỗ nào để đi chơi")
   - "activities": Tư vấn về hoạt động (ví dụ: "nên làm gì", "hoạt động gì phù hợp")
   - "general": Tư vấn chung kết hợp nhiều loại trên
3. Xác định địa điểm đề cập trong câu hỏi (`location`), nếu có.
4. Xác định mô tả thời gian trong câu hỏi (`date_description`), nếu có.

Ví dụ:
- User: "hôm nay nên mặc gì" -> { "is_advice_query": true, "advice_type": "clothing", "location": null, "date_description": "hôm nay" }
- User: "đi chơi ở Đà Nẵng ngày mai nên mang theo gì" -> { "is_advice_query": true, "advice_type": "items", "location": "Da Nang", "date_description": "ngày mai" }
- User: "thời tiết Hà Nội cuối tuần có thích hợp để đi chơi ở công viên không" -> { "is_advice_query": true, "advice_type": "places", "location": "Hanoi", "date_description": "cuối tuần" }
- User: "nên làm gì khi trời mưa ở Sài Gòn cuối tuần" -> { "is_advice_query": true, "advice_type": "activities", "location": "Ho Chi Minh City", "date_description": "cuối tuần" }
- User: "tư vấn giúp tôi mai đi Hà Nội nên chuẩn bị thế nào" -> { "is_advice_query": true, "advice_type": "general", "location": "Hanoi", "date_description": "mai" }
- User: "thời tiết Hà Nội hôm nay thế nào" -> { "is_advice_query": false, "advice_type": null, "location": "Hanoi", "date_description": "hôm nay" }

Trả lời DƯỚI DẠNG JSON HỢP LỆ với 4 trường: is_advice_query (boolean), advice_type (string hoặc null), location (string hoặc null), date_description (string hoặc null).
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
            logger.info(f"Kết quả detect_weather_advice_need (raw): {result_str}")

            try:
                result = json.loads(result_str)
                is_advice_query = result.get("is_advice_query", False)
                advice_type = result.get("advice_type") if is_advice_query else None
                location = result.get("location")
                date_description = result.get("date_description")
                
                if is_advice_query and not advice_type:
                    advice_type = "general"  # Mặc định nếu không xác định được
                    
                if is_advice_query and not location:
                    location = "Hanoi"  # Mặc định là Hà Nội
                    
                logger.info(f"Phân tích truy vấn tư vấn '{query}': is_advice_query={is_advice_query}, advice_type='{advice_type}', location='{location}', date_description='{date_description}'")
                return is_advice_query, advice_type, location, date_description

            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"Lỗi giải mã JSON từ detect_weather_advice_need: {e}. Raw: {result_str}")
                return False, "general", None, None
                
        except Exception as e:
            logger.error(f"Lỗi khi gọi OpenAI trong detect_weather_advice_need: {e}", exc_info=True)
            return False, "general", None, None