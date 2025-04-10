from __future__ import annotations

import json
import asyncio
import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from openai import OpenAI
from openai.types.chat import ChatCompletionMessage, ChatCompletionMessageToolCall

from config.settings import openai_model, OPENWEATHERMAP_API_KEY
from config.logging_config import logger
from models.schemas import ChatRequest, ChatResponse, Message, MessageContent
from core.session_manager import session_manager
from services.tools.tools_definitions import available_tools
from services.tools.tool_executor import execute_tool_call
from services.multimedia.audio_service import process_audio, text_to_speech_google
from services.search.search_service import search_and_summarize, detect_search_intent
from services.weather.weather_parser import WeatherQueryParser
from services.weather.weather_advisor import WeatherAdvisor
from services.weather.weather_service import WeatherService, format_weather_for_prompt
from utils.helpers import generate_chat_summary, save_chat_history

router = APIRouter()

@router.post("/chat")
async def chat_endpoint(chat_request: ChatRequest):
    """
    Endpoint chính cho trò chuyện (sử dụng Tool Calling).
    Includes event_data in the response.
    """
    openai_api_key = chat_request.openai_api_key or os.getenv("OPENAI_API_KEY", "")
    tavily_api_key = chat_request.tavily_api_key or os.getenv("TAVILY_API_KEY", "")
    if not openai_api_key or "sk-" not in openai_api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key không hợp lệ")

    session = session_manager.get_session(chat_request.session_id)
    current_member_id = chat_request.member_id or session.get("current_member")
    session["current_member"] = current_member_id

    # --- Message Handling ---
    if chat_request.messages is not None and not session.get("messages"):
         logger.info(f"Loading message history from client for session {chat_request.session_id}")
         session["messages"] = [msg.dict(exclude_none=True) for msg in chat_request.messages]

    message_content_model = chat_request.message
    message_dict = message_content_model.dict(exclude_none=True)
    logger.info(f"Nhận request với content_type: {chat_request.content_type}")
    processed_content_list = []

    if chat_request.content_type == "audio" and message_dict.get("type") == "audio" and message_dict.get("audio_data"):
        processed_audio = process_audio(message_dict, openai_api_key)
        if processed_audio and processed_audio.get("text"):
             processed_content_list.append({"type": "text", "text": processed_audio["text"]})
             logger.info(f"Đã xử lý audio thành text: {processed_audio['text'][:50]}...")
        else:
             logger.error("Xử lý audio thất bại hoặc không trả về text.")
             processed_content_list.append({"type": "text", "text": "[Lỗi xử lý audio]"})

    elif chat_request.content_type == "image" and message_dict.get("type") == "image_url":
        logger.info(f"Đã nhận hình ảnh: {message_dict.get('image_url', {}).get('url', '')[:60]}...")
        if message_dict.get("image_url"):
            processed_content_list.append({"type": "image_url", "image_url": message_dict["image_url"]})
        else:
            logger.error("Content type là image nhưng thiếu image_url.")
            processed_content_list.append({"type": "text", "text": "[Lỗi xử lý ảnh: thiếu URL]"})
        if message_dict.get("text"):
             processed_content_list.append({"type": "text", "text": message_dict["text"]})

    elif message_dict.get("type") == "html":
         if message_dict.get("html"):
             clean_text = re.sub(r'<[^>]*>', ' ', message_dict["html"])
             clean_text = unescape(clean_text)
             clean_text = re.sub(r'\s+', ' ', clean_text).strip()
             processed_content_list.append({"type": "text", "text": clean_text})
             logger.info(f"Đã xử lý HTML thành text: {clean_text[:50]}...")
         else:
             logger.warning("Loại nội dung là html nhưng thiếu trường 'html'.")
             processed_content_list.append({"type": "text", "text": "[Lỗi xử lý HTML: thiếu nội dung]"})

    elif message_dict.get("type") == "text":
        text_content = message_dict.get("text")
        if text_content:
            processed_content_list.append({"type": "text", "text": text_content})
        else:
             logger.warning("Loại nội dung là text nhưng thiếu trường 'text'.")
             # processed_content_list.append({"type": "text", "text": ""}) # Allow empty text?

    else:
         logger.warning(f"Loại nội dung không xác định hoặc thiếu dữ liệu: {message_dict.get('type')}")
         processed_content_list.append({"type": "text", "text": "[Nội dung không hỗ trợ hoặc bị lỗi]"})

    if processed_content_list:
         session["messages"].append({
             "role": "user",
             "content": processed_content_list
         })
    else:
         logger.error("Không thể xử lý nội dung tin nhắn người dùng.")
         # Raise error or return immediately?


    # --- Tool Calling Flow ---
    final_event_data_to_return: Optional[Dict[str, Any]] = None

    try:
        client = OpenAI(api_key=openai_api_key)
        system_prompt_content = build_system_prompt(current_member_id)

        openai_messages = [{"role": "system", "content": system_prompt_content}]
        for msg in session["messages"]:
             message_for_api = {
                 "role": msg["role"],
                 **({ "tool_calls": msg["tool_calls"] } if msg.get("tool_calls") else {}),
                 **({ "tool_call_id": msg.get("tool_call_id") } if msg.get("tool_call_id") else {}),
             }
             msg_content = msg.get("content")
             if isinstance(msg_content, list):
                  message_for_api["content"] = msg_content
             elif isinstance(msg_content, str):
                  message_for_api["content"] = msg_content
             elif msg.get("role") == "tool":
                  message_for_api["content"] = str(msg_content) if msg_content is not None else ""
             else:
                  logger.warning(f"Định dạng content không mong đợi cho role {msg['role']}: {type(msg_content)}. Sử dụng chuỗi rỗng.")
                  message_for_api["content"] = ""
             openai_messages.append(message_for_api)


        # --- Check Search Need ---
        search_result_for_prompt = await check_search_need(
            openai_messages, 
            openai_api_key, 
            tavily_api_key,
            lat=chat_request.latitude,
            lon=chat_request.longitude
        )
        if search_result_for_prompt:
             # Replace or append to system prompt
             openai_messages[0] = {"role": "system", "content": system_prompt_content + search_result_for_prompt}


        logger.info("--- Calling OpenAI API (Potential First Pass) ---")
        logger.debug(f"Messages sent (last 3): {json.dumps(openai_messages[-3:], indent=2, ensure_ascii=False)}")

        first_response = client.chat.completions.create(
            model=openai_model,
            messages=openai_messages,
            tools=available_tools,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=2048
        )

        response_message: ChatCompletionMessage = first_response.choices[0].message
        session["messages"].append(response_message.dict(exclude_none=True))

        # --- Handle Tool Calls ---
        tool_calls = response_message.tool_calls
        if tool_calls:
            logger.info(f"--- Tool Calls Detected: {len(tool_calls)} ---")
            messages_for_second_call = openai_messages + [response_message.dict(exclude_none=True)]

            for tool_call in tool_calls:
                event_data_from_tool, tool_result_content = execute_tool_call(tool_call, current_member_id)

                if event_data_from_tool and final_event_data_to_return is None:
                    if event_data_from_tool.get("action") in ["add", "update", "delete"]:
                        final_event_data_to_return = event_data_from_tool
                        logger.info(f"Captured event_data for response: {final_event_data_to_return}")

                tool_result_message = {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_call.function.name,
                    "content": tool_result_content,
                }
                messages_for_second_call.append(tool_result_message)
                session["messages"].append(tool_result_message)

            logger.info("--- Calling OpenAI API (Second Pass - Summarizing Tool Results) ---")
            logger.debug(f"Messages for second call (last 4): {json.dumps(messages_for_second_call[-4:], indent=2, ensure_ascii=False)}")

            second_response = client.chat.completions.create(
                model=openai_model,
                messages=messages_for_second_call,
                temperature=0.7,
                max_tokens=1024
            )
            final_assistant_message = second_response.choices[0].message
            final_response_content = final_assistant_message.content

            session["messages"].append(final_assistant_message.dict(exclude_none=True))
            logger.info("Tool execution and summary completed.")

        else:
            logger.info("--- No Tool Calls Detected ---")
            final_response_content = response_message.content

        # --- Final Processing & Response ---
        final_html_content = final_response_content if final_response_content else "Tôi đã thực hiện xong yêu cầu của bạn."

        audio_response_b64 = text_to_speech_google(final_html_content)

        if current_member_id:
             summary = await generate_chat_summary(session["messages"], openai_api_key)
             save_chat_history(current_member_id, session["messages"], summary, chat_request.session_id)

        session_manager.update_session(chat_request.session_id, {"messages": session["messages"]})

        last_message_dict = session["messages"][-1] if session["messages"] else {}
        last_assistant_msg_obj = None
        if last_message_dict.get("role") == "assistant":
             try:
                  content = last_message_dict.get("content")
                  content_for_model = []
                  if isinstance(content, str):
                       content_for_model.append(MessageContent(type="html", html=content))
                  elif isinstance(content, list):
                       if all(isinstance(item, dict) and 'type' in item for item in content):
                           content_for_model = [MessageContent(**item) for item in content]
                       else:
                            logger.warning("Assistant message content list has unexpected structure. Converting to text.")
                            content_text = " ".join(map(str, content))
                            content_for_model.append(MessageContent(type="html", html=content_text))
                  else:
                       content_for_model.append(MessageContent(type="html", html=""))

                  last_assistant_msg_obj = Message(
                      role="assistant",
                      content=content_for_model,
                      tool_calls=last_message_dict.get("tool_calls")
                  )
             except Exception as model_err:
                  logger.error(f"Error creating response Message object: {model_err}", exc_info=True)

        if not last_assistant_msg_obj:
             fallback_content = MessageContent(type="html", html="Đã có lỗi xảy ra hoặc không có phản hồi.")
             last_assistant_msg_obj = Message(role="assistant", content=[fallback_content])

        return ChatResponse(
            session_id=chat_request.session_id,
            messages=[last_assistant_msg_obj],
            audio_response=audio_response_b64,
            response_format="html",
            content_type=chat_request.content_type,
            event_data=final_event_data_to_return
        )

    except Exception as e:
        logger.error(f"Lỗi nghiêm trọng trong /chat endpoint: {str(e)}", exc_info=True)
        session_manager.update_session(chat_request.session_id, {"messages": session.get("messages", [])})
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý chat: {str(e)}")


@router.post("/chat/stream")
async def chat_stream_endpoint(chat_request: ChatRequest):
    """
    Endpoint streaming cho trò chuyện (sử dụng Tool Calling).
    Includes event_data in the final completion message.
    """
    openai_api_key = chat_request.openai_api_key or os.getenv("OPENAI_API_KEY", "")
    tavily_api_key = chat_request.tavily_api_key or os.getenv("TAVILY_API_KEY", "")
    if not openai_api_key or "sk-" not in openai_api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key không hợp lệ")

    session = session_manager.get_session(chat_request.session_id)
    current_member_id = chat_request.member_id or session.get("current_member")
    session["current_member"] = current_member_id

    # --- Message Handling ---
    if chat_request.messages is not None and not session.get("messages"):
         logger.info(f"Stream: Loading message history from client for session {chat_request.session_id}")
         session["messages"] = [msg.dict(exclude_none=True) for msg in chat_request.messages]

    message_content_model = chat_request.message
    message_dict = message_content_model.dict(exclude_none=True)
    logger.info(f"Stream: Nhận request với content_type: {chat_request.content_type}")
    processed_content_list = []

    # --- Process incoming message based on content_type ---
    if chat_request.content_type == "audio" and message_dict.get("type") == "audio" and message_dict.get("audio_data"):
        processed_audio = process_audio(message_dict, openai_api_key)
        if processed_audio and processed_audio.get("text"):
             processed_content_list.append({"type": "text", "text": processed_audio["text"]})
             logger.info(f"Stream: Đã xử lý audio thành text: {processed_audio['text'][:50]}...")
        else:
             logger.error("Stream: Xử lý audio thất bại.")
             processed_content_list.append({"type": "text", "text": "[Lỗi xử lý audio]"})

    elif chat_request.content_type == "image" and message_dict.get("type") == "image_url":
        logger.info(f"Stream: Đã nhận hình ảnh: {message_dict.get('image_url', {}).get('url', '')[:60]}...")
        if message_dict.get("image_url"):
            processed_content_list.append({"type": "image_url", "image_url": message_dict["image_url"]})
        else:
            logger.error("Stream: Content type là image nhưng thiếu image_url.")
            processed_content_list.append({"type": "text", "text": "[Lỗi xử lý ảnh: thiếu URL]"})
        if message_dict.get("text"):
             processed_content_list.append({"type": "text", "text": message_dict["text"]})

    elif message_dict.get("type") == "html":
         if message_dict.get("html"):
            clean_text = re.sub(r'<[^>]*>', ' ', message_dict["html"])
            clean_text = unescape(clean_text)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            processed_content_list.append({"type": "text", "text": clean_text})
            logger.info(f"Stream: Đã xử lý HTML thành text: {clean_text[:50]}...")
         else:
             logger.warning("Stream: Loại nội dung là html nhưng thiếu trường 'html'.")
             processed_content_list.append({"type": "text", "text": "[Lỗi xử lý HTML: thiếu nội dung]"})

    elif message_dict.get("type") == "text":
        text_content = message_dict.get("text")
        if text_content:
            processed_content_list.append({"type": "text", "text": text_content})
        else:
             logger.warning("Stream: Loại nội dung là text nhưng thiếu trường 'text'.")

    else:
         logger.warning(f"Stream: Loại nội dung không xác định hoặc thiếu dữ liệu: {message_dict.get('type')}")
         processed_content_list.append({"type": "text", "text": "[Nội dung không hỗ trợ hoặc bị lỗi]"})
    # --- End of message processing ---

    if processed_content_list:
         session["messages"].append({
             "role": "user",
             "content": processed_content_list
         })
    else:
         logger.error("Stream: Không thể xử lý nội dung tin nhắn đến. Không thêm vào lịch sử.")

    # --- Streaming Generator ---
    async def response_stream_generator():
        final_event_data_to_return: Optional[Dict[str, Any]] = None
        client = OpenAI(api_key=openai_api_key)
        system_prompt_content = build_system_prompt(current_member_id)

        openai_messages = [{"role": "system", "content": system_prompt_content}]
        for msg in session["messages"]:
             message_for_api = {
                 "role": msg["role"],
                 **({ "tool_calls": msg["tool_calls"] } if msg.get("tool_calls") else {}),
                 **({ "tool_call_id": msg.get("tool_call_id") } if msg.get("tool_call_id") else {}),
             }
             msg_content = msg.get("content")
             if isinstance(msg_content, list): message_for_api["content"] = msg_content
             elif isinstance(msg_content, str): message_for_api["content"] = msg_content
             elif msg.get("role") == "tool": message_for_api["content"] = str(msg_content) if msg_content is not None else ""
             else: message_for_api["content"] = ""
             openai_messages.append(message_for_api)

        # --- Check Search Need ---
        try:
             search_result_for_prompt = await check_search_need(
                 openai_messages, 
                 openai_api_key, 
                 tavily_api_key,
                 lat=chat_request.latitude,
                 lon=chat_request.longitude
             )
             if search_result_for_prompt:
                  openai_messages[0] = {"role": "system", "content": system_prompt_content + search_result_for_prompt}
        except Exception as search_err:
             logger.error(f"Error during search need check: {search_err}", exc_info=True)

        accumulated_tool_calls = []
        accumulated_assistant_content = ""
        assistant_message_dict_for_session = {"role": "assistant", "content": None, "tool_calls": None}
        tool_call_chunks = {}

        # --- Main Streaming Logic ---
        try:
            logger.info("--- Calling OpenAI API (Streaming - Potential First Pass) ---")
            stream = client.chat.completions.create(
                model=openai_model,
                messages=openai_messages,
                tools=available_tools,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=2048,
                stream=True
            )

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta: continue

                finish_reason = chunk.choices[0].finish_reason

                if delta.content:
                    accumulated_assistant_content += delta.content
                    yield json.dumps({"chunk": delta.content, "type": "html", "content_type": chat_request.content_type}) + "\n"
                    await asyncio.sleep(0)

                if delta.tool_calls:
                    for tc_chunk in delta.tool_calls:
                        index = tc_chunk.index
                        if index not in tool_call_chunks:
                            tool_call_chunks[index] = {"function": {"arguments": ""}}
                        if tc_chunk.id: tool_call_chunks[index]["id"] = tc_chunk.id
                        if tc_chunk.type: tool_call_chunks[index]["type"] = tc_chunk.type
                        if tc_chunk.function:
                             if tc_chunk.function.name: tool_call_chunks[index]["function"]["name"] = tc_chunk.function.name
                             if tc_chunk.function.arguments: tool_call_chunks[index]["function"]["arguments"] += tc_chunk.function.arguments

                if finish_reason:
                    if finish_reason == "tool_calls":
                        logger.info("--- Stream detected tool_calls ---")
                        for index in sorted(tool_call_chunks.keys()):
                             chunk_data = tool_call_chunks[index]
                             if chunk_data.get("id") and chunk_data.get("function", {}).get("name"):
                                  try:
                                       reconstructed_tc = ChatCompletionMessageToolCall(
                                           id=chunk_data["id"],
                                           type='function',
                                           function=chunk_data["function"]
                                       )
                                       accumulated_tool_calls.append(reconstructed_tc)
                                  except Exception as recon_err:
                                       logger.error(f"Error reconstructing tool call at index {index}: {recon_err} - Data: {chunk_data}")
                             else:
                                  logger.error(f"Incomplete data for tool call reconstruction at index {index}: {chunk_data}")

                        if accumulated_tool_calls:
                             assistant_message_dict_for_session["tool_calls"] = [tc.dict() for tc in accumulated_tool_calls]
                             assistant_message_dict_for_session["content"] = accumulated_assistant_content or None
                             logger.info(f"Reconstructed {len(accumulated_tool_calls)} tool calls.")
                        else:
                             logger.error("Tool calls detected by finish_reason, but failed reconstruction.")
                             assistant_message_dict_for_session["content"] = accumulated_assistant_content

                    elif finish_reason == "stop":
                        logger.info("--- Stream finished without tool_calls ---")
                        assistant_message_dict_for_session["content"] = accumulated_assistant_content
                    else:
                         logger.warning(f"Stream finished with reason: {finish_reason}")
                         assistant_message_dict_for_session["content"] = accumulated_assistant_content
                    break

            # --- Execute Tools and Second Stream (if needed) ---
            if accumulated_tool_calls:
                logger.info(f"--- Executing {len(accumulated_tool_calls)} Tool Calls (Non-Streamed) ---")
                # Add the first assistant message (which contained tool calls) to history
                # Check if it was already added, avoid duplicates
                if not session["messages"] or session["messages"][-1].get("tool_calls") != assistant_message_dict_for_session.get("tool_calls"):
                     session["messages"].append(assistant_message_dict_for_session)

                messages_for_second_call = openai_messages + [assistant_message_dict_for_session]

                for tool_call in accumulated_tool_calls:
                    yield json.dumps({"tool_start": tool_call.function.name}) + "\n"; await asyncio.sleep(0.05)
                    event_data_from_tool, tool_result_content = execute_tool_call(tool_call, current_member_id)

                    if event_data_from_tool and final_event_data_to_return is None:
                         if event_data_from_tool.get("action") in ["add", "update", "delete"]:
                              final_event_data_to_return = event_data_from_tool
                              logger.info(f"Captured event_data for stream response: {final_event_data_to_return}")

                    yield json.dumps({"tool_end": tool_call.function.name, "result_preview": tool_result_content[:50]+"..."}) + "\n"; await asyncio.sleep(0.05)

                    tool_result_message = {
                        "tool_call_id": tool_call.id, "role": "tool",
                        "name": tool_call.function.name, "content": tool_result_content,
                    }
                    messages_for_second_call.append(tool_result_message)
                    session["messages"].append(tool_result_message)

                logger.info("--- Calling OpenAI API (Streaming - Second Pass - Summary) ---")
                logger.debug(f"Messages for second stream call (last 4): {json.dumps(messages_for_second_call[-4:], indent=2, ensure_ascii=False)}")
                summary_stream = client.chat.completions.create(
                    model=openai_model, messages=messages_for_second_call,
                    temperature=0.7, max_tokens=1024, stream=True
                )

                final_summary_content = ""
                async for summary_chunk in summary_stream:
                     delta_summary = summary_chunk.choices[0].delta.content if summary_chunk.choices else None
                     if delta_summary:
                          final_summary_content += delta_summary
                          yield json.dumps({"chunk": delta_summary, "type": "html", "content_type": chat_request.content_type}) + "\n"
                          await asyncio.sleep(0)

                # Add final summary message to history
                session["messages"].append({"role": "assistant", "content": final_summary_content})
                final_response_for_tts = final_summary_content if final_summary_content else "Đã xử lý xong."

            else:
                # If no tool calls, the first assistant message is the final one
                # Check if it was already added, avoid duplicates
                if not session["messages"] or session["messages"][-1].get("content") != assistant_message_dict_for_session.get("content"):
                     session["messages"].append(assistant_message_dict_for_session)
                final_response_for_tts = accumulated_assistant_content if accumulated_assistant_content else "Vâng."

            # --- Post-Streaming Processing ---
            logger.info("Generating final audio response...")
            audio_response_b64 = text_to_speech_google(final_response_for_tts)

            if current_member_id:
                 summary = await generate_chat_summary(session["messages"], openai_api_key)
                 save_chat_history(current_member_id, session["messages"], summary, chat_request.session_id)

            session_manager.update_session(chat_request.session_id, {"messages": session["messages"]})

            complete_response = {
                "complete": True,
                "audio_response": audio_response_b64,
                "content_type": chat_request.content_type,
                "event_data": final_event_data_to_return
            }
            yield json.dumps(complete_response) + "\n"
            logger.info("--- Streaming finished successfully ---")

        except Exception as e:
            logger.error(f"Lỗi nghiêm trọng trong quá trình stream: {str(e)}", exc_info=True)
            error_msg = f"Xin lỗi, đã có lỗi xảy ra trong quá trình xử lý: {str(e)}"
            try:
                yield json.dumps({"error": error_msg, "content_type": chat_request.content_type}) + "\n"
            except Exception as yield_err:
                 logger.error(f"Lỗi khi gửi thông báo lỗi stream cuối cùng: {yield_err}")
        finally:
            logger.info("Đảm bảo lưu session sau khi stream kết thúc hoặc gặp lỗi.")
            session_manager.update_session(chat_request.session_id, {"messages": session.get("messages", [])})

    # Return the StreamingResponse object
    return StreamingResponse(
        response_stream_generator(),
        media_type="application/x-ndjson"
    )

async def check_search_need(messages: List[Dict], openai_api_key: str, tavily_api_key: str, lat: Optional[float] = None, lon: Optional[float] = None) -> str:
    """Kiểm tra nhu cầu tìm kiếm từ tin nhắn cuối của người dùng."""
    if not tavily_api_key and not OPENWEATHERMAP_API_KEY: 
        return ""  # Need Tavily for web search or OpenWeatherMap for weather

    last_user_message_content = None
    for message in reversed(messages):
        if message["role"] == "user":
            last_user_message_content = message["content"]
            break

    if not last_user_message_content: 
        return ""

    last_user_text = ""
    if isinstance(last_user_message_content, str):
        last_user_text = last_user_message_content
    elif isinstance(last_user_message_content, list):
        for item in last_user_message_content:
             if isinstance(item, dict) and item.get("type") == "text":
                  last_user_text = item.get("text", "")
                  break

    if not last_user_text: 
        return ""

    logger.info(f"Checking search need for: '{last_user_text[:100]}...'")

    # Check for Weather Advice Query (new)
    if OPENWEATHERMAP_API_KEY:
        is_advice_query, advice_type, location, date_description = await WeatherAdvisor.detect_weather_advice_need(
            last_user_text, openai_api_key
        )
        
        if is_advice_query:
            # Đảm bảo luôn có location (mặc định là Hà Nội)
            if not location:
                location = "Hanoi"
                
            logger.info(f"Phát hiện truy vấn tư vấn thời tiết: type={advice_type}, location={location}, date={date_description}")
            weather_service = WeatherService(OPENWEATHERMAP_API_KEY)
            
            # Lấy dữ liệu thời tiết
            if date_description:
                # Sử dụng DateTimeHandler để phân tích ngày
                target_date = DateTimeHandler.parse_date(date_description)
                
                current_weather, forecast, target_date, date_text = await WeatherQueryParser.get_forecast_for_specific_date(
                    weather_service, location, date_description, lat, lon
                )
                
                if current_weather and forecast:
                    # Kết hợp lời khuyên dựa trên loại truy vấn và dữ liệu thời tiết
                    advice_data = WeatherAdvisor.combine_advice(
                        {"current": current_weather.get("current"), "forecast": forecast.get("forecast")}, 
                        target_date,
                        advice_type
                    )
                    # Định dạng lời khuyên để đưa vào prompt - truyền thêm location
                    advice_text = WeatherAdvisor.format_advice_for_prompt(advice_data, advice_type, location)
                    
                    advice_prompt_addition = f"""
                    \n\n--- TƯ VẤN THỜI TIẾT (DÙNG ĐỂ TRẢ LỜI) ---
                    Người dùng hỏi: "{last_user_text}"
                    
                    {advice_text}
                    --- KẾT THÚC TƯ VẤN THỜI TIẾT ---
                    
                    Hãy sử dụng thông tin tư vấn trên để trả lời câu hỏi của người dùng một cách tự nhiên và hữu ích.
                    Đưa ra lời khuyên chi tiết, cụ thể và phù hợp với tình hình thời tiết hiện tại/dự báo tại {location}.
                    """
                    return advice_prompt_addition
            else:
                # Sử dụng thời tiết hiện tại
                # Đảm bảo luôn có location
                if not location or location.lower() in ["hanoi", "hà nội"]:
                    if lat is not None and lon is not None:
                        weather_data = await weather_service.get_current_weather(lat=lat, lon=lon)
                        forecast_data = await weather_service.get_forecast(lat=lat, lon=lon, days=3)
                    else:
                        location = "Hanoi"
                        weather_data = await weather_service.get_current_weather(location=location)
                        forecast_data = await weather_service.get_forecast(location=location, days=3)
                else:
                    weather_data = await weather_service.get_current_weather(location=location)
                    forecast_data = await weather_service.get_forecast(location=location, days=3)
                
                if weather_data:
                    # Kết hợp lời khuyên dựa trên loại truy vấn và dữ liệu thời tiết
                    advice_data = WeatherAdvisor.combine_advice(
                        {"current": weather_data.get("current"), "forecast": forecast_data.get("forecast")}, 
                        None,
                        advice_type
                    )
                    # Định dạng lời khuyên để đưa vào prompt - truyền thêm location
                    advice_text = WeatherAdvisor.format_advice_for_prompt(advice_data, advice_type, location)
                    
                    advice_prompt_addition = f"""
                    \n\n--- TƯ VẤN THỜI TIẾT (DÙNG ĐỂ TRẢ LỜI) ---
                    Người dùng hỏi: "{last_user_text}"
                    
                    {advice_text}
                    --- KẾT THÚC TƯ VẤN THỜI TIẾT ---
                    
                    Hãy sử dụng thông tin tư vấn trên để trả lời câu hỏi của người dùng một cách tự nhiên và hữu ích.
                    Đưa ra lời khuyên chi tiết, cụ thể và phù hợp với tình hình thời tiết hiện tại/dự báo tại {location}.
                    """
                    return advice_prompt_addition
    
    # Check for Weather Query
    is_weather_query, location, date_description = await WeatherQueryParser.parse_weather_query(last_user_text, openai_api_key)
    
    if is_weather_query and OPENWEATHERMAP_API_KEY:
        # Đảm bảo luôn có location (mặc định là Hà Nội)
        if not location:
            location = "Hanoi"
            
        logger.info(f"Phát hiện truy vấn thời tiết cho địa điểm: '{location}', thời gian: '{date_description}'")
        weather_service = WeatherService(OPENWEATHERMAP_API_KEY)
        
        # Xử lý truy vấn có cả địa điểm và thời gian (dùng DateTimeHandler)
        if date_description:
            current_weather, forecast, target_date, date_text = await WeatherQueryParser.get_forecast_for_specific_date(
                weather_service, location, date_description, lat, lon
            )
            
            if current_weather and forecast and target_date:
                weather_info = WeatherQueryParser.format_weather_for_date(
                    current_weather, forecast, target_date, date_text
                )
                logger.info(f"Đã lấy thông tin thời tiết cho '{location}' vào ngày {date_text}")
            else:
                logger.warning(f"Không thể lấy thông tin thời tiết cho '{location}' vào '{date_description}'")
                weather_info = format_weather_for_prompt(current_weather, forecast)
        else:
            # Xử lý truy vấn chỉ có địa điểm (không có thời gian cụ thể - trả về thời tiết hiện tại)
            if location and location.lower() not in ["hanoi", "hà nội"]:
                logger.info(f"Sử dụng địa điểm từ câu hỏi: {location}")
                weather_data = await weather_service.get_current_weather(location=location)
                forecast_data = await weather_service.get_forecast(location=location, days=3)
            elif lat is not None and lon is not None:
                logger.info(f"Sử dụng tọa độ: lat={lat}, lon={lon}")
                weather_data = await weather_service.get_current_weather(lat=lat, lon=lon)
                forecast_data = await weather_service.get_forecast(lat=lat, lon=lon, days=3)
            else:
                logger.info("Không có địa điểm và tọa độ, sử dụng mặc định Hà Nội")
                location = "Hanoi"
                weather_data = await weather_service.get_current_weather(location=location)
                forecast_data = await weather_service.get_forecast(location=location, days=3)
                
            if not weather_data:
                return f"\n\n--- LỖI THỜI TIẾT: Không thể lấy thông tin thời tiết cho {location}. Hãy báo lại cho người dùng. ---"
                
            weather_info = format_weather_for_prompt(weather_data, forecast_data)
            
        weather_prompt_addition = f"""
        \n\n--- THÔNG TIN THỜI TIẾT (DÙNG ĐỂ TRẢ LỜI) ---
        Người dùng hỏi: "{last_user_text}"
        {weather_info}
        --- KẾT THÚC THÔNG TIN THỜI TIẾT ---
        Hãy sử dụng thông tin thời tiết này để trả lời câu hỏi của người dùng một cách tự nhiên.
        Luôn đề cập rõ khu vực địa lý ({location}) trong câu trả lời.
        Đưa ra lời khuyên phù hợp với điều kiện thời tiết nếu người dùng hỏi về việc nên mặc gì, nên đi đâu, nên làm gì, v.v.
        """
        return weather_prompt_addition

    # Check for General Search Intent - Phần còn lại giữ nguyên
    if tavily_api_key:
         need_search, search_query, is_news_query, is_feng_shui_query = await detect_search_intent(last_user_text, openai_api_key)
         if need_search:
             logger.info(f"Phát hiện nhu cầu tìm kiếm: query='{search_query}', is_news={is_news_query}, is_feng_shui={is_feng_shui_query}")
             domains_to_include = VIETNAMESE_NEWS_DOMAINS if is_news_query else None
             try:
                search_summary = await search_and_summarize(
                    tavily_api_key, search_query, openai_api_key, 
                    include_domains=domains_to_include,
                    is_feng_shui_query=is_feng_shui_query
                )
                search_prompt_addition = f"""
                \n\n--- THÔNG TIN TÌM KIẾM (DÙNG ĐỂ TRẢ LỜI) ---
                Người dùng hỏi: "{last_user_text}"
                Kết quả tìm kiếm và tóm tắt cho truy vấn '{search_query}':
                {search_summary}
                --- KẾT THÚC THÔNG TIN TÌM KIẾM ---
                Hãy sử dụng kết quả tóm tắt này để trả lời câu hỏi của người dùng một cách tự nhiên, trích dẫn nguồn nếu có.
                """
                return search_prompt_addition
             except Exception as search_err:
                  logger.error(f"Lỗi khi tìm kiếm/tóm tắt cho '{search_query}': {search_err}", exc_info=True)
                  return "\n\n--- LỖI TÌM KIẾM: Không thể lấy thông tin. Hãy báo lại cho người dùng. ---"

    # No search need detected
    logger.info("Không phát hiện nhu cầu tìm kiếm đặc biệt.")
    return ""

def build_system_prompt(current_member_id=None):
    """Xây dựng system prompt cho trợ lý gia đình (sử dụng Tool Calling)."""
    from database.data_manager import family_data, events_data, notes_data
    
    # Start with the base persona and instructions
    system_prompt_parts = [
        "Bạn là trợ lý gia đình thông minh, đa năng và thân thiện tên là HGDS. Nhiệm vụ của bạn là giúp quản lý thông tin gia đình, sự kiện, ghi chú, trả lời câu hỏi, tìm kiếm thông tin, phân tích hình ảnh, và cung cấp thông tin thời tiết.",
        "Giao tiếp tự nhiên, lịch sự và theo phong cách trò chuyện bằng tiếng Việt.",
        "Sử dụng định dạng HTML đơn giản cho phản hồi văn bản (thẻ p, b, i, ul, li, h3, h4, br).",
        "Bạn có thể cung cấp thông tin thời tiết và đưa ra lời khuyên dựa trên thời tiết khi được hỏi.",
        f"Hôm nay là {datetime.datetime.now().strftime('%A, %d/%m/%Y')}.",
        "\n**Các Công Cụ Có Sẵn:**",
        "Bạn có thể sử dụng các công cụ sau khi cần thiết để thực hiện yêu cầu của người dùng:",
        "- `add_family_member`: Để thêm thành viên mới.",
        "- `update_preference`: Để cập nhật sở thích cho thành viên đã biết.",
        "- `add_event`: Để thêm sự kiện mới. Hãy cung cấp mô tả ngày theo lời người dùng (ví dụ: 'ngày mai', 'thứ 6 tuần sau') vào `date_description`, hệ thống sẽ tính ngày chính xác. Bao gồm mô tả lặp lại (ví dụ 'hàng tuần') trong `description` nếu có.",
        "**QUAN TRỌNG VỀ LẶP LẠI:** Chỉ bao gồm mô tả sự lặp lại (ví dụ 'hàng tuần', 'mỗi tháng') trong trường `description` **KHI VÀ CHỈ KHI** người dùng **nêu rõ ràng** ý muốn lặp lại. Nếu người dùng chỉ nói một ngày cụ thể (ví dụ 'thứ 3 tới'), thì **KHÔNG được tự ý thêm** 'hàng tuần' hay bất kỳ từ lặp lại nào vào `description`; sự kiện đó là MỘT LẦN (ONCE)."
        "- `update_event`: Để sửa sự kiện. Cung cấp `event_id` và các trường cần thay đổi. Tương tự `add_event` về cách xử lý ngày (`date_description`) và lặp lại (`description`).",
        "**QUAN TRỌNG VỀ LẶP LẠI:** Nếu cập nhật `description`, chỉ đưa thông tin lặp lại vào đó nếu người dùng **nêu rõ ràng**. Nếu người dùng chỉ thay đổi sang một ngày cụ thể, **KHÔNG tự ý** thêm thông tin lặp lại."
        "- `delete_event`: Để xóa sự kiện.",
        "- `add_note`: Để tạo ghi chú mới.",
        "\n**QUY TẮC QUAN TRỌNG:**",
        "1.  **Chủ động sử dụng công cụ:** Khi người dùng yêu cầu rõ ràng (thêm, sửa, xóa, tạo...), hãy sử dụng công cụ tương ứng.",
        "2.  **Xử lý ngày/giờ:** KHÔNG tự tính toán ngày YYYY-MM-DD. Hãy gửi mô tả ngày của người dùng (ví dụ 'ngày mai', '20/7', 'thứ 3 tới') trong trường `date_description` của công cụ `add_event` hoặc `update_event`. Nếu sự kiện lặp lại, hãy nêu rõ trong trường `description` (ví dụ 'học tiếng Anh thứ 6 hàng tuần').",
        "3.  **Tìm kiếm và thời tiết:** Sử dụng thông tin tìm kiếm và thời tiết được cung cấp trong context (đánh dấu bằng --- THÔNG TIN ---) để trả lời các câu hỏi liên quan. Đừng gọi công cụ nếu thông tin đã có sẵn.",
        "4.  **Phân tích hình ảnh:** Khi nhận được hình ảnh, hãy mô tả nó và liên kết với thông tin gia đình nếu phù hợp.",
        "5.  **Xác nhận:** Sau khi sử dụng công cụ thành công (nhận được kết quả từ 'tool role'), hãy thông báo ngắn gọn cho người dùng biết hành động đã được thực hiện dựa trên kết quả đó. Nếu tool thất bại, hãy thông báo lỗi một cách lịch sự.",
        "6. **Độ dài phản hồi:** Giữ phản hồi cuối cùng cho người dùng tương đối ngắn gọn và tập trung vào yêu cầu chính, trừ khi được yêu cầu chi tiết.",
        "7. **Thời tiết:** Khi được hỏi về thời tiết hoặc lời khuyên liên quan đến thời tiết, sử dụng thông tin thời tiết được cung cấp để trả lời một cách chính xác và hữu ích."
    ]

    # Add current user context
    member_context = ""
    if current_member_id and current_member_id in family_data:
        current_member = family_data[current_member_id]
        member_context = f"""
        \n**Thông Tin Người Dùng Hiện Tại:**
        - ID: {current_member_id}
        - Tên: {current_member.get('name')}
        - Tuổi: {current_member.get('age', 'Chưa biết')}
        - Sở thích: {json.dumps(current_member.get('preferences', {}), ensure_ascii=False)}
        (Hãy cá nhân hóa tương tác và ghi nhận hành động dưới tên người dùng này. Sử dụng ID '{current_member_id}' khi cần `member_id`.)
        """
        system_prompt_parts.append(member_context)
    else:
         system_prompt_parts.append("\n(Hiện tại đang tương tác với khách.)")


    # Add data context
    recent_events_summary = {}
    try:
         sorted_event_ids = sorted(
             events_data.keys(),
             key=lambda eid: events_data[eid].get("created_on", ""),
             reverse=True
         )
         for eid in sorted_event_ids[:3]:
              event = events_data[eid]
              recent_events_summary[eid] = f"{event.get('title')} ({event.get('date')})"
    except Exception as sort_err:
         logger.error(f"Error summarizing recent events: {sort_err}")
         recent_events_summary = {"error": "Không thể tóm tắt"}

    data_context = f"""
    \n**Dữ Liệu Hiện Tại (Tóm tắt):**
    *   Thành viên (IDs): {json.dumps(list(family_data.keys()), ensure_ascii=False)}
    *   Sự kiện gần đây (IDs & Titles): {json.dumps(recent_events_summary, ensure_ascii=False)} (Tổng cộng: {len(events_data)})
    *   Ghi chú (Tổng cộng): {len(notes_data)}
    (Sử dụng ID sự kiện từ tóm tắt này khi cần `event_id` cho việc cập nhật hoặc xóa.)
    """
    system_prompt_parts.append(data_context)

    return "\n".join(system_prompt_parts)