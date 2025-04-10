from __future__ import annotations

import re
import datetime
import dateparser
from typing import Optional, List, Dict, Any, Union, Tuple
from dateutil.relativedelta import relativedelta

from config.settings import VIETNAMESE_WEEKDAY_MAP, NEXT_WEEK_KEYWORDS, RECURRING_KEYWORDS
from config.logging_config import logger

def get_date_from_relative_term(term: str) -> Optional[str]:
    """
    Chuyển đổi từ mô tả tương đối về ngày thành ngày thực tế (YYYY-MM-DD).
    Hỗ trợ: hôm nay/nay/tối nay/sáng nay..., ngày mai/mai, ngày kia/mốt,
    hôm qua, thứ X tuần này/sau/tới, DD/MM, DD/MM/YYYY.
    """
    if not term:
        logger.warning("get_date_from_relative_term called with empty term.")
        return None

    term = term.lower().strip()
    today = datetime.date.today()
    logger.debug(f"Calculating date for term: '{term}', today is: {today.strftime('%Y-%m-%d %A')}")

    # --- 1. Direct relative terms ---
    if term in ["hôm nay", "today", "nay", "tối nay", "sáng nay", "chiều nay", "trưa nay"]:
        logger.info(f"Term '{term}' interpreted as today: {today.strftime('%Y-%m-%d')}")
        return today.strftime("%Y-%m-%d")
    if term in ["ngày mai", "mai", "tomorrow"]:
        calculated_date = today + datetime.timedelta(days=1)
        logger.info(f"Term '{term}' interpreted as tomorrow: {calculated_date.strftime('%Y-%m-%d')}")
        return calculated_date.strftime("%Y-%m-%d")
    if term in ["ngày kia", "mốt", "ngày mốt", "day after tomorrow"]:
        calculated_date = today + datetime.timedelta(days=2)
        logger.info(f"Term '{term}' interpreted as day after tomorrow: {calculated_date.strftime('%Y-%m-%d')}")
        return calculated_date.strftime("%Y-%m-%d")
    if term in ["hôm qua", "yesterday"]:
        calculated_date = today - datetime.timedelta(days=1)
        logger.info(f"Term '{term}' interpreted as yesterday: {calculated_date.strftime('%Y-%m-%d')}")
        # Note: Returning past date might need special handling depending on use case (e.g., for events)
        return calculated_date.strftime("%Y-%m-%d")

    # --- 2. Specific weekdays (upcoming or next week) ---
    target_weekday = -1
    is_next_week = False
    term_for_weekday_search = term

    # Check for "next week" indicators
    for kw in NEXT_WEEK_KEYWORDS:
        if kw in term:
            is_next_week = True
            term_for_weekday_search = term.replace(kw, "").strip()
            logger.debug(f"Detected 'next week' in '{term}', searching for weekday in '{term_for_weekday_search}'")
            break

    # Find the target weekday number
    for day_str, day_num in VIETNAMESE_WEEKDAY_MAP.items():
        if re.search(r'\b' + re.escape(day_str) + r'\b', term_for_weekday_search):
            target_weekday = day_num
            logger.debug(f"Found target weekday: {day_str} ({target_weekday}) in '{term_for_weekday_search}'")
            break

    if target_weekday != -1:
        today_weekday = today.weekday() # Monday is 0, Sunday is 6

        if is_next_week:
            days_to_next_monday = (7 - today_weekday) % 7
            if days_to_next_monday == 0 and today_weekday == 0: days_to_next_monday = 7
            base_date_for_next_week = today + datetime.timedelta(days=days_to_next_monday)
            final_date = base_date_for_next_week + datetime.timedelta(days=target_weekday)
        else: # Upcoming weekday
            days_ahead = (target_weekday - today_weekday + 7) % 7
            if days_ahead == 0: days_ahead = 7 # Assume next week if asking for today's weekday name
            final_date = today + datetime.timedelta(days=days_ahead)

        logger.info(f"Calculated date for '{term}' ({'next week' if is_next_week else 'upcoming'} weekday {target_weekday}): {final_date.strftime('%Y-%m-%d %A')}")
        return final_date.strftime("%Y-%m-%d")

    # --- 3. General future terms (without specific day) ---
    if any(kw in term for kw in NEXT_WEEK_KEYWORDS):
        days_to_next_monday = (7 - today.weekday()) % 7
        if days_to_next_monday == 0: days_to_next_monday = 7
        calculated_date = today + datetime.timedelta(days=days_to_next_monday)
        logger.info(f"Calculated date for general 'next week': {calculated_date.strftime('%Y-%m-%d')} (Next Monday)")
        return calculated_date.strftime("%Y-%m-%d")
    if "tháng tới" in term or "tháng sau" in term or "next month" in term:
         next_month_date = (today.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
         logger.info(f"Calculated date for 'next month': {next_month_date.strftime('%Y-%m-%d')}")
         return next_month_date.strftime("%Y-%m-%d")

    # --- 4. Explicit date formats ---
    try:
        # YYYY-MM-DD
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', term):
             parsed_date = datetime.datetime.strptime(term, "%Y-%m-%d").date()
             logger.info(f"Term '{term}' matched YYYY-MM-DD format.")
             return parsed_date.strftime("%Y-%m-%d")
        # DD/MM/YYYY or D/M/YYYY
        if re.fullmatch(r'\d{1,2}/\d{1,2}/\d{4}', term):
             parsed_date = datetime.datetime.strptime(term, "%d/%m/%Y").date()
             logger.info(f"Term '{term}' matched DD/MM/YYYY format, normalized.")
             return parsed_date.strftime("%Y-%m-%d")
        # DD/MM or D/M (assume current year or next year if past)
        if re.fullmatch(r'\d{1,2}/\d{1,2}', term):
             day, month = map(int, term.split('/'))
             current_year = today.year
             try:
                  parsed_date = datetime.date(current_year, month, day)
                  if parsed_date < today:
                       parsed_date = datetime.date(current_year + 1, month, day)
                       logger.info(f"Term '{term}' (DD/MM) is past, assumed year {current_year + 1}.")
                  else:
                       logger.info(f"Term '{term}' (DD/MM) assumed current year {current_year}.")
                  return parsed_date.strftime("%Y-%m-%d")
             except ValueError:
                  logger.warning(f"Term '{term}' (DD/MM) resulted in an invalid date.")
                  pass

    except ValueError as date_parse_error:
        logger.warning(f"Term '{term}' resembled a date format but failed parsing: {date_parse_error}")
        pass

    # --- 5. Fallback ---
    logger.warning(f"Could not interpret relative date term: '{term}'. Returning None.")
    return None

def date_time_to_cron(date_str, time_str="19:00"):
    """Chuyển ngày giờ cụ thể sang Quartz cron expression."""
    try:
        if not time_str or ':' not in time_str: time_str = "19:00"
        hour, minute = map(int, time_str.split(":"))
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        quartz_cron = f"0 {minute} {hour} {date_obj.day} {date_obj.month} ? {date_obj.year}"
        logger.info(f"Generated Quartz cron ONCE for {date_str} {time_str}: {quartz_cron}")
        return quartz_cron
    except (ValueError, TypeError) as e:
        logger.error(f"Lỗi tạo cron expression ONCE cho date='{date_str}', time='{time_str}': {e}")
        return ""

def determine_repeat_type(description, title):
    """Xác định kiểu lặp lại dựa trên mô tả và tiêu đề."""
    combined_text = (str(description) + " " + str(title)).lower()
    
    # Kiểm tra các mẫu đặc biệt của sự kiện lặp lại
    weekday_patterns = [
        r"\b(tất cả|mọi|các)\b.*\b(thứ \d|thứ hai|thứ ba|thứ tư|thứ năm|thứ sáu|thứ bảy|chủ nhật|t\d|cn)\b",
        r"\b(vào|mỗi)\b.*\b(thứ \d|thứ hai|thứ ba|thứ tư|thứ năm|thứ sáu|thứ bảy|chủ nhật|t\d|cn)\b"
    ]
    
    for pattern in weekday_patterns:
        if re.search(pattern, combined_text):
            logger.info(f"Phát hiện mẫu lặp lại đặc biệt '{pattern}' trong '{combined_text[:100]}...' -> RECURRING")
            return "RECURRING"
    
    # Kiểm tra danh sách từ khóa
    for keyword in RECURRING_KEYWORDS:
        if re.search(r'\b' + re.escape(keyword) + r'\b', combined_text):
            logger.info(f"Phát hiện từ khóa lặp lại '{keyword}' -> RECURRING")
            return "RECURRING"
    
    logger.info(f"Không tìm thấy từ khóa lặp lại trong '{combined_text[:100]}...' -> ONCE")
    return "ONCE"

def generate_recurring_cron(description, title, time_str="19:00"):
    """Tạo Quartz cron expression cho sự kiện lặp lại."""
    try:
        if not time_str or ':' not in time_str: time_str = "19:00"
        hour, minute = map(int, time_str.split(":"))
        combined_text = (str(description) + " " + str(title)).lower()

        # 1. Daily
        if "hàng ngày" in combined_text or "mỗi ngày" in combined_text or "daily" in combined_text:
            quartz_cron = f"0 {minute} {hour} ? * * *"
            logger.info(f"Tạo cron Quartz HÀNG NGÀY lúc {time_str}: {quartz_cron}")
            return quartz_cron

        # 2. Weekly on specific day
        quartz_day_map = {
            "chủ nhật": 1, "cn": 1, "sunday": 1, "thứ 2": 2, "t2": 2, "monday": 2,
            "thứ 3": 3, "t3": 3, "tuesday": 3, "thứ 4": 4, "t4": 4, "wednesday": 4,
            "thứ 5": 5, "t5": 5, "thursday": 5, "thứ 6": 6, "t6": 6, "friday": 6,
            "thứ 7": 7, "t7": 7, "saturday": 7
        }
        found_day_num = None
        found_day_text = ""
        for day_text, day_num in quartz_day_map.items():
            if re.search(r'\b' + re.escape(day_text) + r'\b', combined_text):
                found_day_num = day_num
                found_day_text = day_text
                break
        if found_day_num is not None:
             is_weekly = any(kw in combined_text for kw in ["hàng tuần", "mỗi tuần", "weekly", "every"])
             if is_weekly or any(kw in combined_text for kw in RECURRING_KEYWORDS):
                 quartz_cron = f"0 {minute} {hour} ? * {found_day_num} *"
                 logger.info(f"Tạo cron Quartz HÀNG TUẦN vào Thứ {found_day_text} ({found_day_num}) lúc {time_str}: {quartz_cron}")
                 return quartz_cron
             else:
                  logger.warning(f"Tìm thấy '{found_day_text}' nhưng không rõ là hàng tuần. Không tạo cron lặp lại.")

        # 3. Monthly
        monthly_match = re.search(r"(ngày\s+(\d{1,2})|ngày\s+cuối\s+cùng)\s+(hàng\s+tháng|mỗi\s+tháng)", combined_text)
        if monthly_match:
            day_specifier = monthly_match.group(1)
            day_of_month = "L" if "cuối cùng" in day_specifier else ""
            if not day_of_month:
                day_num_match = re.search(r'\d{1,2}', day_specifier)
                if day_num_match: day_of_month = day_num_match.group(0)

            if day_of_month:
                quartz_cron = f"0 {minute} {hour} {day_of_month} * ? *"
                logger.info(f"Tạo cron Quartz HÀNG THÁNG vào ngày {day_of_month} lúc {time_str}: {quartz_cron}")
                return quartz_cron

        # 4. Fallback
        logger.warning(f"Không thể xác định lịch lặp lại cụ thể từ '{combined_text[:100]}...'. Cron sẽ rỗng.")
        return ""

    except Exception as e:
        logger.error(f"Lỗi khi tạo cron Quartz lặp lại: {e}", exc_info=True)
        return ""

class DateTimeHandler:
    """Lớp xử lý ngày giờ sử dụng dateparser với hỗ trợ nâng cao cho tiếng Việt."""

    # Ánh xạ thứ tiếng Việt
    VIETNAMESE_WEEKDAY_MAP = VIETNAMESE_WEEKDAY_MAP
    
    # Ánh xạ thời gian trong ngày tiếng Việt
    VIETNAMESE_TIME_OF_DAY = {
        "sáng": {"start_hour": 6, "end_hour": 11, "default_hour": 8},
        "trưa": {"start_hour": 11, "end_hour": 14, "default_hour": 12},
        "chiều": {"start_hour": 14, "end_hour": 18, "default_hour": 16},
        "tối": {"start_hour": 18, "end_hour": 22, "default_hour": 19},
        "đêm": {"start_hour": 22, "end_hour": 6, "default_hour": 22},
    }
    
    # Từ khóa thời gian tương đối tiếng Việt
    VIETNAMESE_RELATIVE_TIME = {
        "hôm nay": 0,
        "bây giờ": 0,
        "hiện tại": 0,
        "nay": 0, 
        "ngày mai": 1,
        "mai": 1,
        "ngày mốt": 2,
        "mốt": 2,
        "ngày kia": 2,
        "hôm qua": -1,
        "qua": -1,
        "hôm kia": -2,
        "tuần này": 0,
        "tuần sau": 7,
        "tuần tới": 7,
        "tuần trước": -7,
        "tháng này": 0,
        "tháng sau": 30,
        "tháng tới": 30,
        "tháng trước": -30,
    }

    # Từ khóa lặp lại
    RECURRING_KEYWORDS = RECURRING_KEYWORDS

    # Cài đặt mặc định cho dateparser
    DEFAULT_DATEPARSER_SETTINGS = {
        'TIMEZONE': 'Asia/Ho_Chi_Minh',
        'RETURN_AS_TIMEZONE_AWARE': True,
        'PREFER_DAY_OF_MONTH': 'current',
        'PREFER_DATES_FROM': 'future',
        'DATE_ORDER': 'DMY',
        'STRICT_PARSING': False,
        'RELATIVE_BASE': datetime.datetime.now()
    }

    @classmethod
    def parse_date(cls, date_description: str, base_date: Optional[datetime.datetime] = None) -> Optional[datetime.date]:
        """
        Phân tích mô tả ngày thành đối tượng datetime.date.
        Hỗ trợ tiếng Việt và các mô tả tương đối.

        Args:
            date_description: Mô tả ngày (ví dụ: "ngày mai", "thứ 6 tuần sau", "25/12/2024")
            base_date: Ngày cơ sở để tính toán tương đối (mặc định là hôm nay)

        Returns:
            datetime.date hoặc None nếu không thể phân tích
        """
        if not date_description:
            logger.warning("Mô tả ngày rỗng.")
            return None

        date_description = date_description.lower().strip()
        today = base_date.date() if base_date else datetime.date.today()

        # 0. Xử lý nhanh các từ khóa thời gian trong ngày (sáng nay, tối nay, etc.) - Giữ nguyên
        for time_of_day in cls.VIETNAMESE_TIME_OF_DAY.keys():
            if f"{time_of_day} nay" in date_description or date_description == time_of_day:
                logger.info(f"Phát hiện thời điểm trong ngày: '{time_of_day} nay/nay' -> ngày hôm nay")
                return today

        # 1. Xử lý trực tiếp các từ khóa thời gian tương đối đặc biệt tiếng Việt - Giữ nguyên
        for rel_time, days_offset in cls.VIETNAMESE_RELATIVE_TIME.items():
            # Check for exact match or start of string to avoid partial matches in longer descriptions
            if rel_time == date_description or date_description.startswith(f"{rel_time} "):
                result_date = today + datetime.timedelta(days=days_offset)
                logger.info(f"Phát hiện từ khóa tương đối '{rel_time}' -> {result_date}")
                return result_date

        # --- START: DI CHUYỂN KHỐI XỬ LÝ THỨ LÊN TRÊN ---
        # 3. Xử lý các trường hợp đặc biệt tiếng Việt (ƯU TIÊN TÊN THỨ)
        try:
            # Xử lý thứ trong tuần (ƯU TIÊN HÀNG ĐẦU)
            for weekday_name, weekday_num in cls.VIETNAMESE_WEEKDAY_MAP.items():
                # Use regex for whole word matching to avoid partial matches (e.g., "thứ 2" vs "thứ 20")
                if re.search(r'\b' + re.escape(weekday_name) + r'\b', date_description):
                    is_next_week = "tuần sau" in date_description or "tuần tới" in date_description
                    current_weekday = today.weekday() # Monday is 0, Sunday is 6

                    if is_next_week:
                        # Tính ngày thứ X tuần sau
                        days_to_next_monday = (7 - current_weekday) % 7
                        # If today is Monday, next Monday is 7 days later
                        if days_to_next_monday == 0: days_to_next_monday = 7

                        next_monday = today + datetime.timedelta(days=days_to_next_monday)
                        target_date = next_monday + datetime.timedelta(days=weekday_num)
                    else:
                        # Tính ngày thứ X gần nhất trong tương lai
                        days_ahead = (weekday_num - current_weekday + 7) % 7
                        # If asking for today's weekday name, assume next week's
                        if days_ahead == 0:
                             days_ahead = 7

                        target_date = today + datetime.timedelta(days=days_ahead)

                    logger.info(f"Xử lý thủ công (Ưu tiên Thứ): '{date_description}' thành: {target_date}")
                    return target_date # TRẢ VỀ NGAY KHI TÌM THẤY THỨ

            # Xử lý "đầu tháng", "cuối tháng", "giữa tháng" (chỉ khi không có thứ)
            if "đầu tháng" in date_description:
                target_day = 5 # Default to 5th
                if "sau" in date_description or "tới" in date_description:
                    target_month_base = today.replace(day=1) + relativedelta(months=1)
                else:
                    target_month_base = today
                    # If it's already past the target day this month, use next month
                    if today.day > target_day + 5: # Add buffer
                         target_month_base = today.replace(day=1) + relativedelta(months=1)
                return target_month_base.replace(day=target_day)


            if "giữa tháng" in date_description:
                target_day = 15
                if "sau" in date_description or "tới" in date_description:
                     target_month_base = today.replace(day=1) + relativedelta(months=1)
                else:
                     target_month_base = today
                     if today.day > target_day + 5: # Add buffer
                          target_month_base = today.replace(day=1) + relativedelta(months=1)
                return target_month_base.replace(day=target_day)

            if "cuối tháng" in date_description:
                if "sau" in date_description or "tới" in date_description:
                    base_for_last_day = today.replace(day=1) + relativedelta(months=1)
                else:
                    base_for_last_day = today
                last_day_of_month = (base_for_last_day.replace(day=1) + relativedelta(months=1, days=-1)).day
                return base_for_last_day.replace(day=last_day_of_month)


            # Xử lý định dạng DD/MM hoặc D/M (chỉ khi không có thứ)
            if re.fullmatch(r'\d{1,2}/\d{1,2}', date_description):
                day, month = map(int, date_description.split('/'))

                try:
                    parsed_date = datetime.date(today.year, month, day)
                    # Nếu ngày đã qua trong năm nay, sử dụng năm sau
                    if parsed_date < today:
                        parsed_date = datetime.date(today.year + 1, month, day)

                    logger.info(f"Xử lý định dạng DD/MM '{date_description}' thành: {parsed_date}")
                    return parsed_date
                except ValueError as date_err:
                    logger.warning(f"Ngày không hợp lệ từ DD/MM '{date_description}': {date_err}")
                    # Fall through to dateparser or return None

        except Exception as e:
            logger.warning(f"Xử lý thủ công gặp lỗi với '{date_description}': {e}")
            # Fall through to dateparser or return None

        # --- END: DI CHUYỂN KHỐI XỬ LÝ THỨ LÊN TRÊN ---


        # 2. Thử dùng dateparser (SAU KHI ĐÃ KIỂM TRA THỨ)
        settings = cls.DEFAULT_DATEPARSER_SETTINGS.copy()
        if base_date:
            settings['RELATIVE_BASE'] = base_date

        # Tăng cường PREFER_DATES_FROM để dateparser ít ưu tiên ngày trong tháng hơn khi có từ khác
        # settings['PREFER_DATES_FROM'] = 'future' # Giữ nguyên hoặc thử 'relative-future'

        try:
            # Add some fixes for Vietnamese time expressions
            dp_input = date_description
            # Replace 'tối nay' etc. only if they affect date parsing significantly
            # Removed the replacement here as time is handled separately

            parsed_date_obj = dateparser.parse(
                dp_input,
                languages=['vi', 'en'],
                settings=settings
            )

            if parsed_date_obj:
                # Convert timezone-aware datetime from dateparser to simple date
                parsed_date = parsed_date_obj.date()
                logger.info(f"Dateparser phân tích '{date_description}' thành: {parsed_date}")
                return parsed_date
        except Exception as e:
            logger.warning(f"Dateparser gặp lỗi khi phân tích '{date_description}': {e}")


        # 4. Xử lý đặc biệt cho các mô tả thời gian của ngày (nếu chỉ có thời gian) - Giữ nguyên
        for time_of_day in cls.VIETNAMESE_TIME_OF_DAY.keys():
             # Check for exact match to avoid matching parts of other words
             if date_description == time_of_day:
                 logger.info(f"Phát hiện chỉ có thời điểm trong ngày: '{time_of_day}' -> Giả định ngày hôm nay")
                 return today

        # 5. Trả về None nếu không thể phân tích - Giữ nguyên
        logger.warning(f"Không thể phân tích mô tả ngày: '{date_description}'")
        return None
    
    @classmethod
    def format_date(cls, date_obj: datetime.date) -> str:
        """
        Định dạng đối tượng datetime.date thành chuỗi ISO YYYY-MM-DD.
        
        Args:
            date_obj: Đối tượng datetime.date
            
        Returns:
            Chuỗi định dạng YYYY-MM-DD
        """
        if not date_obj:
            return None
        return date_obj.strftime("%Y-%m-%d")
    
    @classmethod
    def determine_repeat_type(cls, description: str, title: str) -> str:
        """
        Xác định kiểu lặp lại dựa trên mô tả và tiêu đề.
        
        Args:
            description: Mô tả sự kiện
            title: Tiêu đề sự kiện
            
        Returns:
            "RECURRING" hoặc "ONCE"
        """
        combined_text = (str(description) + " " + str(title)).lower()
        
        for keyword in cls.RECURRING_KEYWORDS:
            if re.search(r'\b' + re.escape(keyword) + r'\b', combined_text):
                logger.info(f"Phát hiện từ khóa lặp lại '{keyword}' -> RECURRING")
                return "RECURRING"
                
        logger.info(f"Không tìm thấy từ khóa lặp lại -> ONCE")
        return "ONCE"
    
    @classmethod
    def generate_cron_expression(cls, date_str: str, time_str: str, repeat_type: str, 
                                description: str, title: str) -> str:
        """
        Tạo biểu thức Quartz cron dựa trên thông tin sự kiện.
        
        Args:
            date_str: Ngày định dạng YYYY-MM-DD
            time_str: Thời gian định dạng HH:MM
            repeat_type: Kiểu lặp lại ("RECURRING" hoặc "ONCE")
            description: Mô tả sự kiện
            title: Tiêu đề sự kiện
            
        Returns:
            Biểu thức Quartz cron
        """
        try:
            if not time_str or ':' not in time_str:
                time_str = "19:00"
                
            hour, minute = map(int, time_str.split(":"))
            
            if repeat_type == "RECURRING":
                combined_text = (str(description) + " " + str(title)).lower()
                
                # 1. Hàng ngày
                if "hàng ngày" in combined_text or "mỗi ngày" in combined_text or "daily" in combined_text:
                    cron = f"0 {minute} {hour} ? * * *"
                    logger.info(f"Tạo cron Quartz HÀNG NGÀY lúc {time_str}: {cron}")
                    return cron
                
                # 2. Hàng tuần vào thứ cụ thể
                quartz_day_map = {
                    "chủ nhật": 1, "cn": 1, "sunday": 1, "thứ 2": 2, "t2": 2, "monday": 2,
                    "thứ 3": 3, "t3": 3, "tuesday": 3, "thứ 4": 4, "t4": 4, "wednesday": 4,
                    "thứ 5": 5, "t5": 5, "thursday": 5, "thứ 6": 6, "t6": 6, "friday": 6,
                    "thứ 7": 7, "t7": 7, "saturday": 7
                }
                
                for day_text, day_num in quartz_day_map.items():
                    if re.search(r'\b' + re.escape(day_text) + r'\b', combined_text):
                        is_weekly = any(kw in combined_text for kw in ["hàng tuần", "mỗi tuần", "weekly", "every"])
                        
                        if is_weekly or any(kw in combined_text for kw in cls.RECURRING_KEYWORDS):
                            cron = f"0 {minute} {hour} ? * {day_num} *"
                            logger.info(f"Tạo cron Quartz HÀNG TUẦN vào Thứ {day_text} ({day_num}) lúc {time_str}: {cron}")
                            return cron
                
                # 3. Hàng tháng vào ngày cụ thể
                monthly_match = re.search(r"(ngày\s+(\d{1,2})|ngày\s+cuối\s+cùng)\s+(hàng\s+tháng|mỗi\s+tháng)", combined_text)
                if monthly_match:
                    day_specifier = monthly_match.group(1)
                    day_of_month = "L" if "cuối cùng" in day_specifier else ""
                    if not day_of_month:
                        day_num_match = re.search(r'\d{1,2}', day_specifier)
                        if day_num_match:
                            day_of_month = day_num_match.group(0)
                    
                    if day_of_month:
                        cron = f"0 {minute} {hour} {day_of_month} * ? *"
                        logger.info(f"Tạo cron Quartz HÀNG THÁNG vào ngày {day_of_month} lúc {time_str}: {cron}")
                        return cron
                
                # 4. Fallback: mặc định không cron nếu không xác định được
                logger.warning(f"Không thể xác định lịch lặp lại cụ thể. Cron sẽ rỗng.")
                return ""
                
            else:  # ONCE - Một lần
                if not date_str:
                    logger.warning("Không có ngày cho sự kiện một lần. Cron sẽ rỗng.")
                    return ""
                    
                try:
                    date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                    cron = f"0 {minute} {hour} {date_obj.day} {date_obj.month} ? {date_obj.year}"
                    logger.info(f"Tạo cron Quartz MỘT LẦN cho {date_str} {time_str}: {cron}")
                    return cron
                except ValueError as e:
                    logger.error(f"Lỗi định dạng ngày '{date_str}' khi tạo cron một lần: {e}")
                    return ""
        
        except Exception as e:
            logger.error(f"Lỗi khi tạo biểu thức cron: {e}")
            return ""
    
    @classmethod
    def extract_time_from_date_description(cls, date_description: str) -> Tuple[str, str]:
        """
        Trích xuất thời gian (nếu có) từ mô tả ngày và trả về mô tả ngày đã làm sạch.
        
        Args:
            date_description: Mô tả ngày có thể chứa thời gian
            
        Returns:
            Tuple (cleaned_date_description, time_str)
            - time_str sẽ là None nếu không tìm thấy thời gian
        """
        cleaned_description = date_description.lower().strip()
        time_str = None
        
        # 1. Tìm định dạng giờ:phút
        time_pattern = r'(\d{1,2})[:\.](\d{2})(\s*(?:am|pm|sáng|chiều|tối|đêm))?'
        time_match = re.search(time_pattern, cleaned_description)
        if time_match:
            hour = int(time_match.group(1))
            minute = time_match.group(2)
            ampm = time_match.group(3)
            
            # Xử lý AM/PM
            if ampm:
                ampm = ampm.strip().lower()
                if any(pm in ampm for pm in ['pm', 'chiều', 'tối', 'đêm']) and hour < 12:
                    hour += 12
                elif any(am in ampm for pm in ['am', 'sáng']) and hour == 12:
                    hour = 0
            
            time_str = f"{hour:02d}:{minute}"
            # Loại bỏ phần thời gian từ mô tả
            cleaned_description = cleaned_description.replace(time_match.group(0), "").strip()
            logger.info(f"Đã trích xuất thời gian '{time_str}' từ mô tả '{date_description}'")
            
        # 2. Tìm thời điểm trong ngày (sáng, trưa, chiều, tối, đêm)
        else:
            for time_of_day, time_info in cls.VIETNAMESE_TIME_OF_DAY.items():
                if time_of_day in cleaned_description:
                    hour = time_info['default_hour']
                    time_str = f"{hour:02d}:00"
                    logger.info(f"Đã ánh xạ '{time_of_day}' thành thời gian '{time_str}'")
                    break
        
        return cleaned_description, time_str
    
    @classmethod
    def parse_and_process_event_date(cls, date_description: str, time_str: str = "19:00", 
                                    description: str = "", title: str = "") -> Tuple[str, str, str]:
        """
        Phân tích mô tả ngày và tạo ngày chuẩn cùng biểu thức cron.
        
        Args:
            date_description: Mô tả ngày (vd: "ngày mai", "thứ 6 tuần sau")
            time_str: Thời gian định dạng HH:MM
            description: Mô tả sự kiện
            title: Tiêu đề sự kiện
            
        Returns:
            Tuple (date_str, repeat_type, cron_expression)
        """
        # Trích xuất thời gian từ mô tả ngày nếu có
        cleaned_date_description, extracted_time = cls.extract_time_from_date_description(date_description)
        
        # Ưu tiên thời gian đã trích xuất
        if extracted_time:
            time_str = extracted_time
        
        # Phân tích ngày
        date_obj = cls.parse_date(cleaned_date_description)
        date_str = cls.format_date(date_obj) if date_obj else None
        
        if not date_str:
            logger.warning(f"Không thể xác định ngày từ mô tả: '{date_description}'")
            return None, "ONCE", ""
            
        repeat_type = cls.determine_repeat_type(description, title)
        cron_expression = cls.generate_cron_expression(date_str, time_str, repeat_type, description, title)
        
        logger.info(f"Kết quả xử lý ngày giờ - Mô tả: '{date_description}', Kết quả: {date_str} {time_str}, Lặp lại: {repeat_type}")
        return date_str, repeat_type, cron_expression