
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from ..core.pdf_utils import save_and_convert_if_pdf

router = APIRouter(tags=["upload"])

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if file.content_type not in ("application/pdf", "image/png", "image/jpeg"):
        raise HTTPException(status_code=400, detail="Only PDF, PNG or JPG are supported")

    session_id = str(uuid.uuid4())
    try:
        page_paths = await save_and_convert_if_pdf(file, session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {e}")

    return JSONResponse({"session_id": session_id, "pages": page_paths})
