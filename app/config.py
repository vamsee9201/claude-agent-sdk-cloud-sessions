from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str
    GCP_PROJECT_ID: str = ""
    FIRESTORE_COLLECTION: str = "sessions"
    CLAUDE_MAX_TURNS: int = 10
    CLAUDE_MAX_BUDGET_USD: float = 0.50
    CLAUDE_MODEL: str = "claude-haiku-4-5-20251001"
    CLAUDE_SYSTEM_PROMPT: str = "You are a helpful assistant with access to weather information."
    PORT: int = 8080

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
