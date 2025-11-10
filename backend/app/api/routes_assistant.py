
from typing import List, Dict, Any
from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..core.assistant_client import chat_with_graph

router = APIRouter(tags=["assistant"])

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    session_id: str
    messages: List[ChatMessage]

@router.post("/assistant/chat")
async def assistant_chat(payload: ChatRequest = Body(...)):
    messages: List[Dict[str, Any]] = [m.model_dump() for m in payload.messages]
    result = chat_with_graph(payload.session_id, messages)
    return JSONResponse(result)
