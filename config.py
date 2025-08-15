from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    GEMINI_API_KEY: str = os.getenv('GEMINI_API_KEY', '')
    E2B_API_KEY: str = os.getenv('E2B_API_KEY', '')
    ALLOWED_ORIGINS: list[str] = ["*"] # Example for a frontend
    AGENT_MODEL: str = "gemini-2.5-flash"
    SANDBOX_TIMEOUT_SECONDS: int = 600
    MAX_RETRY_ATTEMPTS: int = 3

settings = Settings()