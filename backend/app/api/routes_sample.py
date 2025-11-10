
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import os

from ..core.config import settings

router = APIRouter(tags=["sample"])

@router.get("/sample/c4")
async def get_sample_c4():
    session_id = "sample_c4"
    session_dir = os.path.join(settings.UPLOAD_ROOT, session_id)
    if not os.path.isdir(session_dir):
        # If somehow missing, return empty but valid payload
        return JSONResponse({ "session_id": session_id, "pages": [] })
    files = sorted(
        [f for f in os.listdir(session_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
    )
    pages = [f"/static/{session_id}/{fname}" for fname in files]
    return JSONResponse({"session_id": session_id, "pages": pages})
