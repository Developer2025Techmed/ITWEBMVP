# config.py
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load .env file. This ensures that when 'settings' is imported,
# the environment variables from .env are already loaded.
load_dotenv()

class AppSettings(BaseSettings):
    MONGO_URI: str
    JWT_SECRET_KEY: str
    OPENAI_API_KEY: str
    ALLOWED_ORIGIN: str = "http://localhost:8081" # Default if not in .env
    APP_NAME: str = "BUA MVP Backend"
    API_PREFIX: str = "/api"
    # Example: If you wanted ACCESS_TOKEN_EXPIRE_MINUTES in .env
    # ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        env_file = ".env"  # Specify the .env file to load
        extra = "ignore"   # Ignore extra fields not defined in AppSettings

settings = AppSettings()

# Optional: You can add debug prints here if you want to confirm loading during startup
# print(f"DEBUG CONFIG.PY: settings.MONGO_URI loaded: {bool(settings.MONGO_URI)}")
# print(f"DEBUG CONFIG.PY: settings.JWT_SECRET_KEY loaded: {bool(settings.JWT_SECRET_KEY)}")
# print(f"DEBUG CONFIG.PY: settings.OPENAI_API_KEY loaded: {bool(settings.OPENAI_API_KEY)}")
