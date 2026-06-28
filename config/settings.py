from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram
    TELEGRAM_BOT_TOKEN: str

    # Groq API
    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Whisper локальный
    WHISPER_MODEL_SIZE: str = "base"

    # Edge TTS
    EDGE_TTS_VOICE: str = "en-US-JennyNeural"

    # FastAPI backend URL
    BACKEND_URL: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
