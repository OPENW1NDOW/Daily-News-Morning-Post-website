from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    jwt_secret: str = ""
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    proxy_url: str = "http://127.0.0.1:7890"
    database_url: str = "sqlite:///./data/news.db"
    rsshub_base_url: str = "http://localhost:1200"
    rsshub_auto_start: bool = True
    rsshub_dir: str = ""
    x_auth_token: str = ""
    x_ct0: str = ""
    bird_bin: str = "bird"
    x_following_candidate_top_n: int = 8


settings = Settings()

