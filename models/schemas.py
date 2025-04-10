from __future__ import annotations

from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union, Tuple

class MessageContent(BaseModel):
    type: str
    text: Optional[str] = None
    html: Optional[str] = None
    image_url: Optional[Dict[str, str]] = None # Expects {"url": "data:..."}
    audio_data: Optional[str] = None # Base64 encoded

class Message(BaseModel):
    role: str
    content: Union[str, List[MessageContent], None] = None # Allow str for simple text, list for multimodal
    tool_calls: Optional[List[Dict[str, Any]]] = None # For assistant messages with tool calls
    tool_call_id: Optional[str] = None # For tool role messages

class ChatRequest(BaseModel):
    session_id: str
    member_id: Optional[str] = None
    message: MessageContent  # The new message from user
    content_type: str = "text"  # "text", "image", "audio"
    openai_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    messages: Optional[List[Message]] = None  # Optional full history from client

class ChatResponse(BaseModel):
    session_id: str
    messages: List[Message] # Return only the *last* assistant message(s)
    audio_response: Optional[str] = None
    response_format: Optional[str] = "html"
    content_type: Optional[str] = "text" # Reflect back the input type
    event_data: Optional[Dict[str, Any]] = None # Include event data if generated

class MemberModel(BaseModel):
    name: str
    age: Optional[str] = None
    preferences: Optional[Dict[str, str]] = None

class EventModel(BaseModel):
    title: str
    date: str # Expects YYYY-MM-DD
    time: Optional[str] = "19:00"
    description: Optional[str] = None
    participants: Optional[List[str]] = None

class NoteModel(BaseModel):
    title: str
    content: str
    tags: Optional[List[str]] = None

class SearchRequest(BaseModel):
    query: str
    tavily_api_key: str
    openai_api_key: str
    is_news_query: Optional[bool] = None

class SuggestedQuestionsResponse(BaseModel):
    session_id: str
    member_id: Optional[str] = None
    suggested_questions: List[str]
    timestamp: str