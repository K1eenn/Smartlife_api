from __future__ import annotations

# Tool Definitions (JSON Schema)
available_tools = [
    {
        "type": "function",
        "function": {
            "name": "add_family_member",
            "description": "Thêm một thành viên mới vào danh sách gia đình.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Tên đầy đủ của thành viên."},
                    "age": {"type": "string", "description": "Tuổi của thành viên (ví dụ: '30', 'khoảng 10')."},
                    "preferences": {
                        "type": "object",
                        "description": "Sở thích của thành viên (ví dụ: {'food': 'Phở', 'hobby': 'Đọc sách'}).",
                        "properties": {
                            "food": {"type": "string", "description": "Món ăn yêu thích."},
                            "hobby": {"type": "string", "description": "Sở thích chính."},
                            "color": {"type": "string", "description": "Màu sắc yêu thích."}
                        },
                         "additionalProperties": {"type": "string"}
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_preference",
            "description": "Cập nhật một sở thích cụ thể cho một thành viên gia đình đã biết.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member_id": {"type": "string", "description": "ID của thành viên cần cập nhật (lấy từ thông tin gia đình trong context)."},
                    "preference_key": {"type": "string", "description": "Loại sở thích cần cập nhật (ví dụ: 'food', 'hobby', 'color')."},
                    "preference_value": {"type": "string", "description": "Giá trị mới cho sở thích đó."}
                },
                "required": ["member_id", "preference_key", "preference_value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_event",
            "description": "Thêm một sự kiện mới vào lịch gia đình. Hệ thống sẽ tự động tính toán ngày chính xác từ mô tả.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Tiêu đề của sự kiện."},
                    "date_description": {"type": "string", "description": "Mô tả về ngày diễn ra sự kiện THEO LỜI NGƯỜI DÙNG (ví dụ: 'ngày mai', 'thứ 6 tuần sau', '25/12/2024', '20/7'). Không tự tính toán ngày."},
                    "time": {"type": "string", "description": "Thời gian diễn ra sự kiện (HH:MM). Mặc định là 19:00 nếu không được cung cấp.", "default": "19:00"},
                    "description": {"type": "string", "description": "Mô tả chi tiết về sự kiện, bao gồm cả thông tin lặp lại nếu có (ví dụ: 'Họp gia đình hàng tháng', 'học tiếng Anh mỗi tối thứ 6')."},
                    "participants": {"type": "array", "items": {"type": "string"}, "description": "Danh sách tên những người tham gia."}
                },
                "required": ["title", "date_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_event",
            "description": "Cập nhật thông tin cho một sự kiện đã tồn tại trong lịch.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "ID của sự kiện cần cập nhật (lấy từ danh sách sự kiện trong context)."},
                    "title": {"type": "string", "description": "Tiêu đề mới cho sự kiện."},
                    "date_description": {"type": "string", "description": "Mô tả MỚI về ngày diễn ra sự kiện THEO LỜI NGƯỜI DÙNG (nếu thay đổi)."},
                    "time": {"type": "string", "description": "Thời gian mới (HH:MM)."},
                    "description": {"type": "string", "description": "Mô tả chi tiết mới, bao gồm thông tin lặp lại nếu có."},
                    "participants": {"type": "array", "items": {"type": "string"}, "description": "Danh sách người tham gia mới."}
                },
                "required": ["event_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_event",
            "description": "Xóa một sự kiện khỏi lịch gia đình.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "ID của sự kiện cần xóa (lấy từ danh sách sự kiện trong context)."}
                },
                "required": ["event_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_note",
            "description": "Thêm một ghi chú mới.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Tiêu đề của ghi chú."},
                    "content": {"type": "string", "description": "Nội dung chi tiết của ghi chú."},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Danh sách các thẻ (tags) liên quan đến ghi chú."}
                },
                "required": ["title", "content"]
            }
        }
    }
]