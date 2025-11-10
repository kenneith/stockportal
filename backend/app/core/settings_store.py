import os
import json
from typing import Any, Dict

from .config import settings as base_settings

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "data", "settings.json")

_DEFAULTS: Dict[str, Any] = {
    "vlm_provider": base_settings.VLM_PROVIDER,
    "openai_api_key": base_settings.OPENAI_API_KEY or "",
    "openai_vlm_model": "gpt-4.1-mini",
    "neo4j_uri": "",
    "neo4j_user": "",
    "neo4j_password": "",
    "pdf_dpi": 200,
}


def load_settings() -> Dict[str, Any]:
    """讀取設定檔，如不存在或損壞則回傳預設值。"""
    if not os.path.exists(SETTINGS_FILE):
        return dict(_DEFAULTS)

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return dict(_DEFAULTS)
    except Exception:
        return dict(_DEFAULTS)

    merged: Dict[str, Any] = dict(_DEFAULTS)
    for k, v in data.items():
        if v is not None:
            merged[k] = v
    return merged


def save_settings(new_settings: Dict[str, Any]) -> Dict[str, Any]:
    """儲存設定檔，回傳實際寫入的合併結果。"""
    merged: Dict[str, Any] = dict(_DEFAULTS)
    for k, v in new_settings.items():
        if v is not None:
            merged[k] = v

    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    return merged
