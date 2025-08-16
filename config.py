from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    gemini_api_key: str = ""
    app_env: str = "production"
    log_level: str = "INFO"
    max_error_iterations: int = 10
    code_exec_timeout: int = 600


settings = Settings()
