import os
import base64
from typing import Dict, Any, Optional

from .config import settings
from .vlm_stub import analyze_page_stub
from .settings_store import load_settings

try:
    from openai import OpenAI
except ImportError:  # optional dependency
    OpenAI = None  # type: ignore


async def analyze_page(
    session_id: str,
    page_index: int,
    page_type: Optional[str],
    prompt: Optional[str],
) -> Dict[str, Any]:
    """
    Main VLM entry point.

    Provider selection 順序：
    1. 先讀取 settings_store（使用者在前端 UI 調整的設定）：vlm_provider / openai_api_key / openai_vlm_model
    2. 若上述未設定，再退回環境變數 config.Settings 裡的預設值。
    - provider == 'openai' 且有 API key，才會呼叫 OpenAI Responses API
    - 否則一律使用本地 stub，方便開發除錯。
    """
    cfg = load_settings()
    provider = cfg.get("vlm_provider") or settings.VLM_PROVIDER
    api_key = cfg.get("openai_api_key") or settings.OPENAI_API_KEY

    # Fallback to stub if provider 不是 openai，或缺少 openai 套件 / API key
    if provider != "openai" or OpenAI is None or not api_key:
        return await analyze_page_stub(session_id, page_index, page_type, prompt)

    model_name = cfg.get("openai_vlm_model") or "gpt-4.1-mini"

    client = OpenAI(api_key=api_key)

    # 嘗試從本機上傳目錄讀取對應的頁面圖片，優先轉成 base64 data URL 給 OpenAI 使用
    # pdf_utils 會將頁面輸出為 page_001.png, page_002.png ...，而這裡的 page_index 為 0-based
    session_dir = os.path.join(settings.UPLOAD_ROOT, session_id)
    img_filename = f"page_{page_index + 1:03d}.png"
    img_path = os.path.join(session_dir, img_filename)

    image_url: str
    if os.path.exists(img_path):
        try:
            with open(img_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            image_url = f"data:image/png;base64,{b64}"
        except Exception:
            # 若讀檔失敗，退回以本機 URL 字串表示（仍為合法 image_url 型別）
            image_url = f"http://127.0.0.1:8000/static/{session_id}/{img_filename}"
    else:
        # 找不到對應檔案時，仍給一個 URL 字串（可能導致 OpenAI 端抓圖失敗，但不會因型別錯誤而 400）
        image_url = f"http://127.0.0.1:8000/static/{session_id}/{img_filename}"

    user_prompt = prompt or "請閱讀這張結構圖，並輸出 JSON 格式的鋼構構件估料資料。"

    try:
        response = client.responses.create(
            model=model_name,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_prompt},
                        {
                            "type": "input_image",
                            "image_url": image_url,
                        },
                    ],
                }
            ],
            max_output_tokens=2048,
        )
    except Exception as e:  # 若呼叫失敗，退回 stub，避免整體流程中斷
        return {
            "session_id": session_id,
            "page_index": page_index,
            "page_type": page_type,
            "prompt": prompt,
            "status": "error",
            "provider": "openai",
            "error": str(e),
            "raw_text": "",
            "parsed_data": {},
        }

    # 將 Responses API 的輸出整理成純文字（簡化版本）
    content_text = ""
    try:
        for item in response.output:
            if getattr(item, "type", None) == "message":
                msg = item.message
                for part in getattr(msg, "content", []):
                    if getattr(part, "type", None) == "output_text":
                        content_text += getattr(part, "text", "")
    except Exception:
        # 若解析失敗，就直接轉成字串
        content_text = str(response)

    return {
        "session_id": session_id,
        "page_index": page_index,
        "page_type": page_type,
        "prompt": prompt,
        "status": "ok",
        "provider": "openai",
        "model": model_name,
        "image_url": image_url,
        "raw_text": content_text,
        "parsed_data": {
            "note": "目前僅回傳模型輸出的原始文字（預期為 JSON），後續可在後端加上 JSON 解析與欄位驗證。",
        },
    }
