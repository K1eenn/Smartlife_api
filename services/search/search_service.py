from __future__ import annotations

import json
import asyncio
import datetime
import requests
from typing import Dict, Any, List, Optional, Tuple

from config.settings import VIETNAMESE_NEWS_DOMAINS, openai_model
from config.logging_config import logger

async def detect_search_intent(query: str, api_key: str) -> Tuple[bool, str, bool, bool]:
    """Phát hiện ý định tìm kiếm (async wrapper)."""
    if not api_key or not query: return False, query, False, False

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        current_date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        system_prompt = f"""
Bạn là một hệ thống phân loại và tinh chỉnh câu hỏi thông minh. Nhiệm vụ của bạn là:
1. Xác định xem câu hỏi có cần tìm kiếm thông tin thực tế, tin tức mới hoặc dữ liệu cập nhật không (`need_search`). Câu hỏi về kiến thức chung, định nghĩa đơn giản thường không cần tìm kiếm.
2. Nếu cần tìm kiếm, hãy tinh chỉnh câu hỏi thành một truy vấn tìm kiếm tối ưu (`search_query`), bao gồm yếu tố thời gian nếu có (hôm nay, 26/03...).
3. Xác định xem câu hỏi có chủ yếu về tin tức, thời sự, thể thao, sự kiện hiện tại không (`is_news_query`). Câu hỏi về giá cả, sản phẩm, hướng dẫn KHÔNG phải là tin tức.
4. Xác định xem câu hỏi có liên quan đến phong thủy, ngày tốt xấu, ngày thuận lợi, ngày may mắn không (`is_feng_shui_query`). Các câu hỏi như "ngày nào thuận lợi", "ngày nào tốt", "ngày đẹp" đều được xem là yêu cầu về phong thủy.

Hôm nay là ngày: {current_date_str}.

CHÚ Ý QUAN TRỌNG: Các câu hỏi về thời tiết (ví dụ: "thời tiết ở Hà Nội", "trời có mưa không") hoặc yêu cầu tư vấn dựa trên thời tiết (ví dụ: "nên mặc gì hôm nay") KHÔNG cần tìm kiếm (`need_search` = false).

Ví dụ:
- User: "tin tức covid hôm nay" -> {{ "need_search": true, "search_query": "tin tức covid mới nhất ngày {current_date_str}", "is_news_query": true, "is_feng_shui_query": false }}
- User: "những ngày nào thuận lợi trong tuần này" -> {{ "need_search": true, "search_query": "ngày tốt xấu phong thủy tuần này từ {current_date_str}", "is_news_query": false, "is_feng_shui_query": true }}
- User: "tuần này tôi có nhiều việc quan trọng, những ngày nào thuận lợi?" -> {{ "need_search": true, "search_query": "ngày tốt xấu phong thủy tuần này từ {current_date_str}", "is_news_query": false, "is_feng_shui_query": true }}
- User: "ngày nào hợp cho việc ký kết hợp đồng" -> {{ "need_search": true, "search_query": "ngày tốt để ký kết hợp đồng theo phong thủy tháng hiện tại", "is_news_query": false, "is_feng_shui_query": true }}
- User: "thủ đô nước Pháp là gì?" -> {{ "need_search": false, "search_query": "thủ đô nước Pháp là gì?", "is_news_query": false, "is_feng_shui_query": false }}
- User: "thời tiết Hà Nội ngày mai" -> {{ "need_search": false, "search_query": "dự báo thời tiết Hà Nội ngày mai", "is_news_query": true, "is_feng_shui_query": false }}

Trả lời DƯỚI DẠNG JSON HỢP LỆ với 4 trường: need_search (boolean), search_query (string), is_news_query (boolean), is_feng_shui_query (boolean).
"""
        response = await asyncio.to_thread(
             client.chat.completions.create,
             model=openai_model,
             messages=[
                 {"role": "system", "content": system_prompt},
                 {"role": "user", "content": f"Câu hỏi của người dùng: \"{query}\""}
             ],
             temperature=0.1,
             max_tokens=150,
             response_format={"type": "json_object"}
        )

        result_str = response.choices[0].message.content
        logger.info(f"Kết quả detect_search_intent (raw): {result_str}")

        try:
            result = json.loads(result_str)
            need_search = result.get("need_search", False)
            search_query = query
            is_news_query = False
            is_feng_shui_query = result.get("is_feng_shui_query", False)

            # Ensure weather-related queries are explicitly marked as need_search=false
            weather_keywords_for_detection = ["thời tiết", "dự báo", "nhiệt độ", "nắng", "mưa", "gió", "mấy độ", "bao nhiêu độ", "mặc gì", "nên đi"]
            if any(keyword in query.lower() for keyword in weather_keywords_for_detection):
                 need_search = False
                 logger.info(f"Detected potential weather query '{query}', overriding need_search to False.")

            if need_search:
                search_query = result.get("search_query", query)
                if not search_query: search_query = query
                is_news_query = result.get("is_news_query", False)

            logger.info(f"Phân tích truy vấn '{query}': need_search={need_search}, search_query='{search_query}', is_news_query={is_news_query}, is_feng_shui_query={is_feng_shui_query}")
            return need_search, search_query, is_news_query, is_feng_shui_query

        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Lỗi giải mã JSON từ detect_search_intent: {e}. Raw: {result_str}")
            return False, query, False, False
    except Exception as e:
        logger.error(f"Lỗi khi gọi OpenAI trong detect_search_intent: {e}", exc_info=True)
        return False, query, False, False

async def tavily_extract(api_key: str, urls: List[str], include_images: bool = False, extract_depth: str = "advanced") -> Optional[Dict[str, Any]]:
    """Trích xuất nội dung từ URL (Wrap sync call)."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {"urls": urls, "include_images": include_images, "extract_depth": extract_depth}
    try:
        response = await asyncio.to_thread(
             requests.post, "https://api.tavily.com/extract", headers=headers, json=data, timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Lỗi Tavily Extract API ({e.__class__.__name__}): {e}")
        return None
    except Exception as e:
         logger.error(f"Lỗi không xác định trong tavily_extract: {e}", exc_info=True)
         return None


async def tavily_search(api_key: str, query: str, search_depth: str = "advanced", max_results: int = 5, 
                         include_domains: Optional[List[str]] = None, exclude_domains: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """Tìm kiếm Tavily (Wrap sync call)."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {"query": query, "search_depth": search_depth, "max_results": max_results}
    if include_domains: data["include_domains"] = include_domains
    if exclude_domains: data["exclude_domains"] = exclude_domains
    try:
        response = await asyncio.to_thread(
            requests.post, "https://api.tavily.com/search", headers=headers, json=data, timeout=15
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Lỗi Tavily Search API ({e.__class__.__name__}): {e}")
        return None
    except Exception as e:
         logger.error(f"Lỗi không xác định trong tavily_search: {e}", exc_info=True)
         return None


async def search_and_summarize(tavily_api_key: str, query: str, openai_api_key: str, 
                               include_domains: Optional[List[str]] = None, is_feng_shui_query: bool = False) -> str:
    """Tìm kiếm và tổng hợp."""
    if not tavily_api_key or not openai_api_key or not query:
        return "Thiếu thông tin API key hoặc câu truy vấn."

    try:
        logger.info(f"Bắt đầu tìm kiếm Tavily cho: '{query}'" + (f" (Domains: {include_domains})" if include_domains else ""))
        
        # Xử lý đặc biệt cho truy vấn phong thủy
        if is_feng_shui_query:
            # Tạo prompt mẫu cho phong thủy thay vì tìm kiếm web
            current_date = datetime.datetime.now()
            end_date = current_date + datetime.timedelta(days=7)
            date_range = f"từ {current_date.strftime('%d/%m/%Y')} đến {end_date.strftime('%d/%m/%Y')}"
            
            feng_shui_prompt = f"""
Hãy phân tích chi tiết về các ngày tốt xấu trong tuần này ({date_range}) dựa trên phong thủy và tử vi. Phân tích cần bao gồm:

1. Đánh giá từng ngày trong tuần:
   - Ngày âm lịch (Can Chi)
   - Mức độ thuận lợi (thang điểm sao từ 1-5)
   - Phù hợp cho những việc gì
   - Không nên làm những việc gì
   - Giờ tốt trong ngày
   - Lưu ý đặc biệt
   - Màu sắc may mắn (nếu có)

2. So sánh các ngày và đưa ra đề xuất ngày tốt nhất cho:
   - Ký kết hợp đồng quan trọng
   - Gặp gỡ đối tác/khách hàng
   - Bắt đầu dự án mới
   - Đi du lịch/công tác

Trình bày thông tin sử dụng HTML đơn giản và định dạng dễ đọc. Thông tin cần chi tiết, chính xác theo học thuyết phong thủy và tử vi.
"""

            try:
                from openai import OpenAI
                client = OpenAI(api_key=openai_api_key)
                
                response = await asyncio.to_thread(
                     client.chat.completions.create,
                     model=openai_model,
                     messages=[
                         {"role": "system", "content": "Bạn là chuyên gia phong thủy và tử vi hàng đầu. Bạn có kiến thức sâu rộng về Ngũ hành, Bát quái, Can Chi, và các học thuyết phong thủy phương Đông. Bạn cung cấp phân tích chi tiết, chính xác và có tính ứng dụng cao về các ngày tốt xấu trong phong thủy."},
                         {"role": "user", "content": feng_shui_prompt}
                     ],
                     temperature=0.7,
                     max_tokens=2000
                )
                
                feng_shui_analysis = response.choices[0].message.content
                logger.info(f"Đã tạo phân tích phong thủy (độ dài: {len(feng_shui_analysis)})")
                return feng_shui_analysis
            except Exception as feng_shui_err:
                logger.error(f"Lỗi khi tạo phân tích phong thủy: {feng_shui_err}", exc_info=True)
                return "Xin lỗi, tôi không thể tạo phân tích phong thủy chi tiết lúc này. Vui lòng thử lại sau."
            
        # Tiếp tục với xử lý tìm kiếm bình thường
        search_results = await tavily_search(
            tavily_api_key, query, include_domains=include_domains, max_results=5
        )

        if not search_results or not search_results.get("results"):
            logger.warning(f"Không tìm thấy kết quả Tavily cho '{query}'")
            return f"Xin lỗi, tôi không tìm thấy kết quả nào cho '{query}'" + (f" trong các trang tin tức được chỉ định." if include_domains else ".")

        urls_to_extract = [result["url"] for result in search_results["results"][:3]]
        if not urls_to_extract:
            logger.warning(f"Không có URL nào để trích xuất từ kết quả Tavily cho '{query}'.")
            return f"Đã tìm thấy một số tiêu đề liên quan đến '{query}' nhưng không thể trích xuất nội dung."

        logger.info(f"Trích xuất nội dung từ URLs: {urls_to_extract}")
        extract_result = await tavily_extract(tavily_api_key, urls_to_extract)

        extracted_contents = []
        if extract_result and extract_result.get("results"):
             for res in extract_result["results"]:
                  content = res.get("raw_content", "")
                  if content:
                       max_len_per_source = 4000
                       content = content[:max_len_per_source] + "..." if len(content) > max_len_per_source else content
                       extracted_contents.append({"url": res.get("url"), "content": content})
                  else:
                       logger.warning(f"Nội dung trống rỗng từ URL: {res.get('url')}")
        else:
             logger.warning(f"Trích xuất nội dung thất bại từ Tavily cho URLs: {urls_to_extract}")
             basic_info = ""
             for res in search_results.get("results", [])[:3]:
                 basic_info += f"- Tiêu đề: {res.get('title', '')}\n URL: {res.get('url')}\n\n"
             if basic_info:
                  return f"Không thể trích xuất chi tiết nội dung, nhưng đây là một số kết quả tìm thấy:\n{basic_info}"
             else:
                  return f"Không thể trích xuất nội dung từ các kết quả tìm kiếm cho '{query}'."

        if not extracted_contents:
             logger.warning(f"Không có nội dung nào được trích xuất thành công cho '{query}'.")
             return f"Không thể trích xuất nội dung chi tiết cho '{query}'."

        logger.info(f"Tổng hợp {len(extracted_contents)} nguồn trích xuất cho '{query}'.")
        
        from openai import OpenAI
        client = OpenAI(api_key=openai_api_key)

        content_for_prompt = ""
        total_len = 0
        max_total_len = 15000
        for item in extracted_contents:
             source_text = f"\n--- Nguồn: {item['url']} ---\n{item['content']}\n--- Hết nguồn ---\n"
             if total_len + len(source_text) > max_total_len:
                  logger.warning(f"Đã đạt giới hạn độ dài context khi tổng hợp, bỏ qua các nguồn sau.")
                  break
             content_for_prompt += source_text
             total_len += len(source_text)

        prompt = f"""
        Dưới đây là nội dung trích xuất từ các trang web liên quan đến câu hỏi: "{query}"

        {content_for_prompt}

        Nhiệm vụ của bạn:
        1.  **Tổng hợp thông tin chính:** Phân tích và tổng hợp các thông tin quan trọng nhất từ các nguồn trên để trả lời cho câu hỏi "{query}".
        2.  **Tập trung vào ngày cụ thể (nếu có):** Nếu câu hỏi đề cập ngày cụ thể, ưu tiên thông tin ngày đó.
        3.  **Trình bày rõ ràng:** Viết một bản tóm tắt mạch lạc, có cấu trúc bằng tiếng Việt.
        4.  **Xử lý mâu thuẫn:** Nếu có thông tin trái ngược, hãy nêu rõ.
        5.  **Nêu nguồn:** Cố gắng trích dẫn nguồn (URL) cho các thông tin quan trọng nếu có thể, ví dụ: "(Nguồn: [URL])".
        6.  **Phạm vi:** Chỉ sử dụng thông tin từ các nguồn được cung cấp. Không thêm kiến thức ngoài.
        7.  **Định dạng:** Sử dụng HTML đơn giản (p, b, ul, li).

        Hãy bắt đầu bản tóm tắt của bạn.
        """

        try:
            response = await asyncio.to_thread(
                 client.chat.completions.create,
                 model=openai_model,
                 messages=[
                     {"role": "system", "content": "Bạn là một trợ lý tổng hợp thông tin chuyên nghiệp. Nhiệm vụ của bạn là tổng hợp nội dung từ các nguồn được cung cấp để tạo ra một bản tóm tắt chính xác, tập trung vào yêu cầu của người dùng và trích dẫn nguồn nếu có thể."},
                     {"role": "user", "content": prompt}
                 ],
                 temperature=0.3,
                 max_tokens=1500
            )
            summarized_info = response.choices[0].message.content
            return summarized_info.strip()

        except Exception as summary_err:
             logger.error(f"Lỗi khi gọi OpenAI để tổng hợp: {summary_err}", exc_info=True)
             return "Xin lỗi, tôi gặp lỗi khi đang tóm tắt thông tin tìm kiếm."

    except Exception as e:
        logger.error(f"Lỗi trong quá trình tìm kiếm và tổng hợp cho '{query}': {e}", exc_info=True)
        return f"Có lỗi xảy ra trong quá trình tìm kiếm và tổng hợp thông tin: {str(e)}"    