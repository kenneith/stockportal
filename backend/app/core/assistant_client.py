
from typing import Dict, Any, List

from .config import settings
from .settings_store import load_settings
from .graph_client import query_project_context

try:
    from openai import OpenAI
except ImportError:  # optional dep
    OpenAI = None  # type: ignore


def _build_system_prompt() -> str:
    return (
        "你是一位熟悉鋼構與RC結構估料的智能助理，會根據 Neo4j 圖譜中的資訊回答問題。"
        "回答時請以專業、簡潔的方式說明，並盡量引用圖紙與構件的語彙。"
    )


def chat_with_graph(session_id: str, messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    使用 Neo4j 圖譜內容作為 context，並視設定決定是否呼叫 OpenAI。
    如果沒有設定 OpenAI，就用簡單規則回覆。
    """
    context = query_project_context(session_id)

    # 若無 OpenAI 或未提供 API key，則以簡單模板回覆
    cfg = load_settings()
    provider = (cfg.get("vlm_provider") or settings.VLM_PROVIDER or "stub").lower()
    api_key = cfg.get("openai_api_key") or settings.OPENAI_API_KEY

    if provider != "openai" or not api_key or OpenAI is None:
        user_last = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_last = m.get("content", "")
                break
        text = "【離線模式】目前尚未連線至 OpenAI，以下為根據圖譜資料的概要說明：\n"
        if context:
            text += f"\n圖譜摘要：\n{context}\n"
        else:
            text += "\n目前圖譜尚未有與此 session 相關的資料，請先進行圖紙解析。\n"
        if user_last:
            text += f"\n你剛剛的提問是：{user_last}"
        return {"answer": text, "provider": "stub", "session_id": session_id}

    # 使用 OpenAI Responses API
    client = OpenAI(api_key=api_key)

    system_prompt = _build_system_prompt()
    # 把圖譜內容塞在 system context 之後
    graph_context_prompt = f"以下是與本工程 session_id={session_id} 相關的圖譜資訊：\n{context}"

    conv_input = [
        {
            "role": "system",
            "content": [
                {"type": "text", "text": system_prompt},
                {"type": "text", "text": graph_context_prompt},
            ],
        }
    ]
    for m in messages:
        conv_input.append(
            {
                "role": m.get("role", "user"),
                "content": [{"type": "text", "text": m.get("content", "")}],
            }
        )

    resp = client.responses.create(
        model="gpt-4.1-mini",
        input=conv_input,
        temperature=0.2,
    )

    text = ""
    if getattr(resp, "output", None):
        first = resp.output[0]
        blocks = getattr(first, "content", [])
        parts = []
        for block in blocks:
            t = getattr(block, "text", None)
            if t:
                parts.append(t)
        text = "".join(parts)

    return {
        "answer": text,
        "provider": "openai",
        "session_id": session_id,
    }
