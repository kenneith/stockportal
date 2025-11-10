
from enum import Enum
from pydantic import BaseModel

class PageType(str, Enum):
    drawing_note = "drawing_note"
    plan = "plan"
    elevation = "elevation"

class PageInfo(BaseModel):
    session_id: str
    page_path: str
    page_index: int
    page_type: PageType | None = None
