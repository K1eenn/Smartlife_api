from __future__ import annotations

import json
import logging
from typing import Dict, Any, Optional, Tuple, List

from openai.types.chat import ChatCompletionMessageToolCall

from config.logging_config import logger
from core.datetime_handler import DateTimeHandler, get_date_from_relative_term, determine_repeat_type
from core.event_manager import classify_event
from services.tools.family_tools import add_family_member, update_preference
from services.tools.event_tools import add_event, update_event, delete_event
from services.tools.note_tools import add_note

# Map tool names to actual Python functions
tool_functions = {
    "add_family_member": add_family_member,
    "update_preference": update_preference,
    "add_event": add_event,
    "update_event": update_event,
    "delete_event": delete_event,
    "add_note": add_note,
}

def execute_tool_call(tool_call: ChatCompletionMessageToolCall, current_member_id: Optional[str]) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Executes the appropriate Python function based on the tool call.
    Handles date calculation and event classification for event tools.
    Returns a tuple: (event_data_for_frontend, tool_result_content_for_llm)
    """
    function_name = tool_call.function.name
    try:
        arguments_str = tool_call.function.arguments
        if not arguments_str:
             arguments = {}
             logger.warning(f"Tool call {function_name} received empty arguments string.")
        else:
             arguments = json.loads(arguments_str)

        logger.info(f"Executing tool: {function_name} with args: {arguments}")

        # --- Special Handling for Event Dates and Classification ---
        final_date_str = None
        repeat_type = "ONCE"
        cron_expression = ""
        event_category = "General" # Default category
        event_action_data = None

        if function_name in ["add_event", "update_event"]:
            date_description = arguments.get("date_description")
            time_str = arguments.get("time", "19:00")
            description = arguments.get("description", "")
            title = arguments.get("title", "") # Cần title để phân loại

            # Lấy title/description cũ nếu update mà không cung cấp cái mới (để phân loại)
            if function_name == "update_event":
                event_id = arguments.get("event_id")
                if event_id and str(event_id) in events_data:
                     event_id_str = str(event_id)
                     if not title: title = events_data[event_id_str].get("title", "")
                     if not description: description = events_data[event_id_str].get("description", "")
                     arguments["id"] = event_id_str # Đảm bảo có id dạng string
                else:
                    # Quan trọng: Trả về lỗi ngay nếu không tìm thấy event ID khi update
                    error_msg = f"Lỗi: Không tìm thấy sự kiện ID '{event_id}' để cập nhật."
                    logger.error(error_msg)
                    return None, error_msg # Trả về tuple (None, error_message)

            # --- Phân loại sự kiện TRƯỚC khi xử lý ngày giờ ---
            event_category = classify_event(title, description) # <<< GỌI HÀM PHÂN LOẠI
            arguments["category"] = event_category # Thêm category vào arguments để lưu
            logger.info(f"Determined event category: '{event_category}' for title: '{title}'")

            # --- Xử lý ngày giờ (giữ nguyên logic cũ) ---
            if date_description:
                # Phân tích và xử lý mô tả ngày một lần duy nhất
                final_date_str, repeat_type, cron_expression = DateTimeHandler.parse_and_process_event_date(
                    date_description, time_str, description, title
                )

                if final_date_str:
                    logger.info(f"Ngày đã xử lý: '{final_date_str}' từ mô tả '{date_description}'")
                    arguments["date"] = final_date_str
                else:
                    logger.warning(f"Không thể xác định ngày từ '{date_description}'. Ngày sự kiện sẽ trống hoặc không thay đổi.")
                    # Không xóa date khỏi arguments nếu nó đã tồn tại (trường hợp update không đổi ngày)
                    if "date" not in arguments and function_name == "add_event":
                         pass # Cho phép date là None khi thêm mới nếu là recurring
                    elif "date" in arguments and not final_date_str:
                         # Nếu update mà date_description không parse được, không nên xóa date cũ
                         logger.info(f"Update event: date_description '{date_description}' không hợp lệ, giữ nguyên date cũ nếu có.")
                         # Không cần làm gì thêm, date cũ vẫn trong arguments nếu được truyền
                    elif "date" in arguments and final_date_str is None and event_to_update.get("repeat_type") == "ONCE":
                        # Nếu update sự kiện ONCE mà date_desc không parse đc, nên báo lỗi hoặc giữ ngày cũ thay vì xóa?
                        # Hiện tại đang giữ nguyên date cũ trong arguments nếu có.
                        pass


            # Nếu không có date_description, nhưng là update, cần giữ lại repeat_type cũ nếu có
            elif function_name == "update_event" and event_id_str in events_data:
                 repeat_type = events_data[event_id_str].get("repeat_type", "ONCE")
                 # Lấy lại cron expression cũ nếu không có thay đổi về description/title/time ảnh hưởng cron
                 # Hoặc đơn giản là không cập nhật cron nếu không có date_description/description mới?
                 # Hiện tại: Sẽ không tạo cron mới nếu không có date_description.
                 # Có thể cần logic phức tạp hơn để cập nhật cron nếu chỉ description thay đổi.

            if "date_description" in arguments:
                del arguments["date_description"]

            # Đặt repeat_type đã được xác định (từ date_description hoặc từ event cũ)
            arguments['repeat_type'] = repeat_type

            logger.info(f"Event type: {repeat_type}, Cron generated: '{cron_expression}'")

            # Chuẩn bị data để trả về frontend nếu cần
            event_action_data = {
                "action": "add" if function_name == "add_event" else "update",
                "id": arguments.get("id"), # Sẽ là None cho add, có giá trị cho update
                "title": title,
                "description": description,
                "cron_expression": cron_expression,
                "repeat_type": repeat_type,
                "original_date": final_date_str, # Ngày YYYY-MM-DD đã parse
                "original_time": time_str,
                "participants": arguments.get("participants", []),
                "category": event_category # <<< Thêm category vào dữ liệu trả về
            }

        # --- Assign creator/updater ID ---
        if current_member_id:
            if function_name == "add_event" or function_name == "add_note":
                arguments["created_by"] = current_member_id
            elif function_name == "update_event":
                 arguments["updated_by"] = current_member_id

        # --- Execute the function ---
        if function_name in tool_functions:
            func_to_call = tool_functions[function_name]
            try:
                result = func_to_call(arguments) # arguments giờ đã bao gồm 'category' nếu là event
                if result is False:
                     tool_result_content = f"Thất bại khi thực thi {function_name}. Chi tiết lỗi đã được ghi lại."
                     logger.error(f"Execution failed for tool {function_name} with args {arguments}")
                     event_action_data = None # Reset event data if execution failed
                else:
                     tool_result_content = f"Đã thực thi thành công {function_name}."
                     logger.info(f"Successfully executed tool {function_name}")
                     # Xử lý event_action_data cho delete
                     if function_name == "delete_event":
                         deleted_event_id = arguments.get("event_id")
                         # Cố gắng lấy category của event bị xóa để trả về (nếu cần)
                         deleted_category = events_data.get(str(deleted_event_id), {}).get("category", "Unknown") if str(deleted_event_id) in events_data else "Unknown" # Lấy trước khi pop
                         # Logic xóa thực tế nằm trong hàm delete_event được gọi ở trên
                         # Cập nhật event_action_data sau khi hàm delete_event chạy thành công
                         event_action_data = {
                            "action": "delete",
                            "id": deleted_event_id,
                            "category": deleted_category # Trả về category của event đã xóa
                         }
                         tool_result_content = f"Đã xóa thành công sự kiện ID {deleted_event_id}."

                return event_action_data, tool_result_content
            except Exception as func_exc:
                 logger.error(f"Error executing tool function {function_name}: {func_exc}", exc_info=True)
                 # Giữ lại event_action_data = None ở đây vì tool lỗi
                 return None, f"Lỗi trong quá trình thực thi {function_name}: {str(func_exc)}"
        else:
            logger.error(f"Unknown tool function: {function_name}")
            return None, f"Lỗi: Không tìm thấy hàm cho công cụ {function_name}."

    except json.JSONDecodeError as json_err:
        logger.error(f"Error decoding arguments for {function_name}: {json_err}")
        logger.error(f"Invalid JSON string: {tool_call.function.arguments}")
        return None, f"Lỗi: Dữ liệu cho công cụ {function_name} không hợp lệ (JSON sai định dạng)."
    except Exception as e:
        logger.error(f"Unexpected error in execute_tool_call for {function_name}: {e}", exc_info=True)
        return None, f"Lỗi không xác định khi chuẩn bị thực thi {function_name}."