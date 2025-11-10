
import os
from typing import List
from fastapi import UploadFile
from .config import settings
from .settings_store import load_settings

try:
    from pdf2image import convert_from_bytes
except ImportError:
    convert_from_bytes = None

async def save_and_convert_if_pdf(file: UploadFile, session_id: str, dpi: int = 200) -> List[str]:
    session_dir = os.path.join(settings.UPLOAD_ROOT, session_id)
    os.makedirs(session_dir, exist_ok=True)

    # allow override dpi from settings
    cfg = load_settings()
    try:
        dpi = int(cfg.get('pdf_dpi', dpi) or dpi)
    except Exception:
        dpi = dpi

    raw_bytes = await file.read()
    filename = file.filename or "upload"

    if file.content_type == "application/pdf":
        if convert_from_bytes is None:
            raise RuntimeError("pdf2image is required to process PDF files. Please install pdf2image and poppler.")
        images = convert_from_bytes(raw_bytes, dpi=dpi)
        page_paths = []
        for idx, img in enumerate(images, start=1):
            out_name = f"page_{idx:03d}.png"
            out_path = os.path.join(session_dir, out_name)
            img.save(out_path, "PNG")
            page_paths.append(f"/static/{session_id}/{out_name}")
        return page_paths
    else:
        # treat as single image
        ext = os.path.splitext(filename)[1] or ".png"
        out_name = f"page_001{ext}"
        out_path = os.path.join(session_dir, out_name)
        with open(out_path, "wb") as f:
            f.write(raw_bytes)
        return [f"/static/{session_id}/{out_name}"]
