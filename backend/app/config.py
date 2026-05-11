from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    proxy_url: str = "http://127.0.0.1:7890"
    database_url: str = "sqlite:///./data/news.db"
    rsshub_base_url: str = "http://localhost:1200"
    rsshub_auto_start: bool = True
    rsshub_dir: str = ""


settings = Settings()
