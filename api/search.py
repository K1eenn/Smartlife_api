from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional

from config.logging_config import logger
from models.schemas import SearchRequest
from services.search.search_service import search_and_summarize

router = APIRouter()

@router.post("/search")
async def search_endpoint(search_request: SearchRequest):
    """Tìm kiếm thông tin thời gian thực."""
    if not search_request.tavily_api_key or not search_request.openai_api_key:
        raise HTTPException(status_code=400, detail="Thiếu API key cho tìm kiếm.")

    from config.settings import VIETNAMESE_NEWS_DOMAINS
    domains_to_include = VIETNAMESE_NEWS_DOMAINS if search_request.is_news_query else None
    try:
        result = await search_and_summarize(
            search_request.tavily_api_key,
            search_request.query,
            search_request.openai_api_key,
            include_domains=domains_to_include
        )
        return {"query": search_request.query, "result": result}
    except Exception as e:
         logger.error(f"Lỗi trong search_endpoint: {e}", exc_info=True)
         raise HTTPException(status_code=500, detail=f"Lỗi tìm kiếm: {str(e)}")
    