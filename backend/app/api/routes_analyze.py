
from typing import Optional
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os

from ..core.config import settings
from ..core.session_meta import load_meta, save_meta
from ..core.graph_client import upsert_page_analysis
from ..core.vlm_client import analyze_page
from ..models.page_types import PageType

router = APIRouter(tags=["analyze"])

class AnalyzeRequest(BaseModel):
    page_type: Optional[PageType] = None
    prompt: Optional[str] = None


@router.post("/sessions/{session_id}/pages/{page_index}/analyze")
async def analyze_page_endpoint(session_id: str, page_index: int, payload: AnalyzeRequest = Body(...)):
    # Simple session/page existence check
    session_dir = os.path.join(settings.UPLOAD_ROOT, session_id)
    if not os.path.isdir(session_dir):
        raise HTTPException(status_code=404, detail="Session not found")

    # store meta info
    meta = load_meta(session_id)
    key = str(page_index)
    meta.setdefault(key, {})
    if payload.page_type is not None:
        meta[key]["page_type"] = payload.page_type.value
    if payload.prompt is not None:
        meta[key]["prompt"] = payload.prompt
    save_meta(session_id, meta)

    # call VLM (provider decided by settings.VLM_PROVIDER)
    result = await analyze_page(
        session_id=session_id,
        page_index=page_index,
        page_type=meta[key].get("page_type"),
        prompt=meta[key].get("prompt"),
    )

    # Update Neo4j knowledge graph (if configured)
    try:
        upsert_page_analysis(
            session_id=session_id,
            page_index=page_index,
            page_type=meta[key].get("page_type"),
            result=result,
        )
    except Exception:
        # 圖譜更新失敗不影響主流程
        pass

    return JSONResponse(result)


@router.get("/sessions/{session_id}/pages/meta")
async def get_session_meta(session_id: str):
    session_dir = os.path.join(settings.UPLOAD_ROOT, session_id)
    if not os.path.isdir(session_dir):
        raise HTTPException(status_code=404, detail="Session not found")
    meta = load_meta(session_id)
    return JSONResponse({"session_id": session_id, "meta": meta})
