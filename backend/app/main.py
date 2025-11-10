
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from .core.config import settings
from .api.routes_upload import router as upload_router
from .api.routes_pages import router as pages_router
from .api.routes_analyze import router as analyze_router
from .api.routes_sample import router as sample_router
from .api.routes_settings import router as settings_router
from .api.routes_assistant import router as assistant_router
from .api.routes_report import router as report_router

app = FastAPI(title="SSVMI Backend", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router, prefix="/api")
app.include_router(pages_router, prefix="/api")
app.include_router(analyze_router, prefix="/api")
app.include_router(sample_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(assistant_router, prefix="/api")
app.include_router(report_router, prefix="/api")

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

# Mount static files for page previews
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "uploads")
os.makedirs(static_dir, exist_ok=True)
app.mount(settings.STATIC_URL_PREFIX, StaticFiles(directory=static_dir), name="static")
