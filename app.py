from fastapi import FastAPI, Depends, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import logging
import json
import datetime

# Import config
from config.settings import DATA_DIR
from config.logging_config import logger, setup_logging

# Import database functions
from database.data_manager import load_all_data, verify_data_structure

# Import routers
from api.chat import router as chat_router
from api.family import router as family_router
from api.events import router as events_router
from api.notes import router as notes_router
from api.search import router as search_router
from api.weather import router as weather_router
from api.session import router as session_router
from api.multimedia import router as multimedia_router
from api.history import router as history_router

# Setup app
app = FastAPI(title="Trợ lý Gia đình API (Tool Calling)",
              description="API cho Trợ lý Gia đình thông minh với khả năng xử lý text, hình ảnh, âm thanh và sử dụng Tool Calling, bao gồm thông tin thời tiết qua OpenWeatherMap.",
              version="1.2.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Trong production nên giới hạn origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat_router, tags=["Chat"])
app.include_router(family_router, prefix="/family_members", tags=["Family"])
app.include_router(events_router, prefix="/events", tags=["Events"])
app.include_router(notes_router, prefix="/notes", tags=["Notes"])
app.include_router(search_router, prefix="/search", tags=["Search"])
app.include_router(weather_router, prefix="/weather", tags=["Weather"])
app.include_router(session_router, tags=["Session"])
app.include_router(multimedia_router, tags=["Multimedia"])
app.include_router(history_router, tags=["History"])

@app.get("/")
async def root():
    return {
        "name": "Trợ lý Gia đình API (Tool Calling)", "version": "1.2.0",
        "description": "API cho ứng dụng Trợ lý Gia đình thông minh",
        "endpoints": [
            "/chat", "/chat/stream", "/suggested_questions", 
            "/family_members", "/events", "/notes", 
            "/search", "/weather", "/session", 
            "/analyze_image", "/transcribe_audio", "/tts", 
            "/chat_history/{member_id}"
        ]
    }

@app.on_event("startup")
async def startup_event():
    """Các tác vụ cần thực hiện khi khởi động server."""
    logger.info("Khởi động Family Assistant API server (Tool Calling)")
    # Load data
    load_all_data()
    logger.info("Đã tải dữ liệu và sẵn sàng hoạt động.")

@app.on_event("shutdown")
async def shutdown_event():
    """Các tác vụ cần thực hiện khi đóng server."""
    from database.data_manager import save_data, family_data, events_data, notes_data, chat_history
    from config.settings import FAMILY_DATA_FILE, EVENTS_DATA_FILE, NOTES_DATA_FILE, CHAT_HISTORY_FILE
    from core.session_manager import session_manager
    
    logger.info("Đóng Family Assistant API server...")
    save_data(FAMILY_DATA_FILE, family_data)
    save_data(EVENTS_DATA_FILE, events_data)
    save_data(NOTES_DATA_FILE, notes_data)
    save_data(CHAT_HISTORY_FILE, chat_history)
    session_manager._save_sessions()
    logger.info("Đã lưu dữ liệu. Server tắt.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Trợ lý Gia đình API (Tool Calling)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host IP")
    parser.add_argument("--port", type=int, default=8000, help="Port")
    parser.add_argument("--reload", action="store_true", help="Auto reload server on code changes")
    args = parser.parse_args()

    log_level = "debug" if args.reload else "info"

    logger.info(f"Khởi động Trợ lý Gia đình API (Tool Calling) trên http://{args.host}:{args.port}")

    uvicorn.run(
        "app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=log_level.lower()
    )