
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from ..core.config import settings

router = APIRouter(tags=["pages"])

@router.get("/sessions/{session_id}/pages")
async def list_pages(session_id: str):
    session_dir = os.path.join(settings.UPLOAD_ROOT, session_id)
    if not os.path.isdir(session_dir):
        raise HTTPException(status_code=404, detail="Session not found")

    files = sorted(
        [f for f in os.listdir(session_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
    )
    pages = [f"/static/{session_id}/{fname}" for fname in files]
    return JSONResponse({"session_id": session_id, "pages": pages})
