
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    UPLOAD_ROOT: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "uploads")
    STATIC_URL_PREFIX: str = "/static"

    # VLM / LLM settings
    VLM_PROVIDER: str = os.getenv("VLM_PROVIDER", "stub")  # 'stub' or 'openai'
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")

settings = Settings()
