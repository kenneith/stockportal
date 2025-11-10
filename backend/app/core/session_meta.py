
import os
import json
from typing import Dict, Any
from .config import settings

def _meta_file_path(session_id: str) -> str:
    return os.path.join(settings.UPLOAD_ROOT, session_id, "meta.json")

def load_meta(session_id: str) -> Dict[str, Any]:
    path = _meta_file_path(session_id)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_meta(session_id: str, data: Dict[str, Any]) -> None:
    session_dir = os.path.join(settings.UPLOAD_ROOT, session_id)
    os.makedirs(session_dir, exist_ok=True)
    path = _meta_file_path(session_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
