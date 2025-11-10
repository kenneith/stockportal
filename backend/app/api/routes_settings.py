
from typing import Any, Dict
from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from ..core.settings_store import load_settings, save_settings

router = APIRouter(tags=["settings"])

@router.get("/settings")
async def get_settings():
    data = load_settings()
    return JSONResponse(data)

@router.put("/settings")
async def update_settings(payload: Dict[str, Any] = Body(...)):
    saved = save_settings(payload or {})
    return JSONResponse(saved)
