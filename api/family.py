from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional

from config.logging_config import logger
from models.schemas import MemberModel
from database.data_manager import family_data
from services.tools.family_tools import add_family_member

router = APIRouter()

@router.get("/family_members")
async def get_family_members():
    return family_data

@router.post("/family_members")
async def add_family_member_endpoint(member: MemberModel):
    """Thêm thành viên (qua endpoint trực tiếp)."""
    details = member.dict()
    if add_family_member(details):
         new_member_id = None
         for mid, mdata in family_data.items():
              if mdata.get("name") == member.name and mdata.get("age") == member.age:
                   new_member_id = mid
                   break
         if new_member_id:
             return {"id": new_member_id, "member": family_data[new_member_id]}
         else:
             raise HTTPException(status_code=500, detail="Thêm thành công nhưng không tìm thấy ID.")
    else:
        raise HTTPException(status_code=500, detail="Không thể thêm thành viên.")