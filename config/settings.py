import os
import dotenv

# Tải biến môi trường
dotenv.load_dotenv()

# --- Directory Settings ---
DATA_DIR = os.environ.get("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Đường dẫn file lưu trữ dữ liệu
FAMILY_DATA_FILE = os.path.join(DATA_DIR, "family_data.json")
EVENTS_DATA_FILE = os.path.join(DATA_DIR, "events_data.json")
NOTES_DATA_FILE = os.path.join(DATA_DIR, "notes_data.json")
CHAT_HISTORY_FILE = os.path.join(DATA_DIR, "chat_history.json")
SESSIONS_DATA_FILE = os.path.join(DATA_DIR, "sessions_data.json")

# Thư mục lưu trữ tạm thời
TEMP_DIR = os.path.join(DATA_DIR, "temp_files")
os.makedirs(TEMP_DIR, exist_ok=True)

# --- API Keys ---
OPENAI_API_KEY_ENV = os.getenv("OPENAI_API_KEY", "")
TAVILY_API_KEY_ENV = os.getenv("TAVILY_API_KEY", "")
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")

openai_model = "gpt-4o-mini"  # Or your preferred model supporting Tool Calling

# --- Domains ---
VIETNAMESE_NEWS_DOMAINS = [
    "vnexpress.net", "tuoitre.vn", "thanhnien.vn", "vietnamnet.vn", "vtv.vn",
    "nhandan.vn", "baochinhphu.vn", "laodong.vn", "tienphong.vn", "zingnews.vn",
    "cand.com.vn", "kenh14.vn", "baophapluat.vn",
]

# --- Date/Time Constants ---
VIETNAMESE_WEEKDAY_MAP = {
    "thứ 2": 0, "thứ hai": 0, "t2": 0,
    "thứ 3": 1, "thứ ba": 1, "t3": 1,
    "thứ 4": 2, "thứ tư": 2, "t4": 2,
    "thứ 5": 3, "thứ năm": 3, "t5": 3,
    "thứ 6": 4, "thứ sáu": 4, "t6": 4,
    "thứ 7": 5, "thứ bảy": 5, "t7": 5,
    "chủ nhật": 6, "cn": 6,
}

NEXT_WEEK_KEYWORDS = ["tuần sau", "tuần tới", "next week"]
RECURRING_KEYWORDS = [
    "hàng ngày", "mỗi ngày", "hàng tuần", "mỗi tuần", "hàng tháng", "mỗi tháng",
    "hàng năm", "mỗi năm", "định kỳ", "lặp lại",
    "mỗi sáng thứ", "mỗi trưa thứ", "mỗi chiều thứ", "mỗi tối thứ",
    "thứ 2 hàng tuần", "mỗi thứ 2", "mỗi t2", "thứ 3 hàng tuần", "mỗi thứ 3", "mỗi t3",
    "thứ 4 hàng tuần", "mỗi thứ 4", "mỗi t4", "thứ 5 hàng tuần", "mỗi thứ 5", "mỗi t5",
    "thứ 6 hàng tuần", "mỗi thứ 6", "mỗi t6", "thứ 7 hàng tuần", "mỗi thứ 7", "mỗi t7",
    "chủ nhật hàng tuần", "mỗi chủ nhật", "mỗi cn",
    "daily", "every day", "weekly", "every week", "monthly", "every month",
    "yearly", "annually", "every year", "recurring", "repeating",
    "every monday", "every tuesday", "every wednesday", "every thursday",
    "every friday", "every saturday", "every sunday",
    # Thêm từ khóa mới
    "tất cả", "mọi", "các", "tất cả thứ", "mọi thứ", "các thứ",
    "tất cả tối thứ", "mọi tối thứ", "các tối thứ",
    "tất cả sáng thứ", "mọi sáng thứ", "các sáng thứ",
    "tất cả chiều thứ", "mọi chiều thứ", "các chiều thứ",
    "vào các", "vào tất cả", "vào mọi"
]