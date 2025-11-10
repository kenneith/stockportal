
from typing import Dict, Any, Optional

async def analyze_page_stub(
    session_id: str,
    page_index: int,
    page_type: Optional[str] = None,
    prompt: Optional[str] = None,
) -> Dict[str, Any]:
    # For now just return a dummy payload so frontend can be wired up.
    return {
        "session_id": session_id,
        "page_index": page_index,
        "page_type": page_type,
        "prompt": prompt,
        "status": "stub",
        "parsed_data": {
            "message": "This is a stub response. VLM integration will be implemented later.",
        },
    }
