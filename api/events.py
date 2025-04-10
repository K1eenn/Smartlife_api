from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional

from config.logging_config import logger
from models.schemas import EventModel
from database.data_manager import events_data
from core.datetime_handler import determine_repeat_type
from services.tools.event_tools import add_event
from utils.helpers import filter_events_by_member

router = APIRouter()

@router.get("/events")
async def get_events(member_id: Optional[str] = None):
    if member_id:
        return filter_events_by_member(member_id)
    return events_data

@router.post("/events")
async def add_event_endpoint(event: EventModel, member_id: Optional[str] = None):
    """Thêm sự kiện (qua endpoint trực tiếp)."""
    details = event.dict()
    details["created_by"] = member_id
    details["repeat_type"] = determine_repeat_type(details.get("description"), details.get("title"))

    if add_event(details):
         new_event_id = None
         for eid, edata in events_data.items():
              if (edata.get("title") == event.title and
                  edata.get("date") == event.date and
                  edata.get("created_by") == member_id):
                   new_event_id = eid
                   break
         if new_event_id:
              return {"id": new_event_id, "event": events_data[new_event_id]}
         else:
              raise HTTPException(status_code=500, detail="Thêm sự kiện thành công nhưng không tìm thấy ID.")

    else:
        raise HTTPException(status_code=500, detail="Không thể thêm sự kiện.")