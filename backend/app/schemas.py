from datetime import date, datetime
from pydantic import BaseModel


class NewsItemOut(BaseModel):
    id: int
    date: date
    category: str
    importance: int
    title: str
    summary: str | None
    full_summary: str | None
    viewpoints: list | None
    background: str | None
    source_links: list | None
    is_favorited: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Admin request schemas ──

class SourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    enabled: bool | None = None
    use_proxy: bool | None = None


class XAccountEnabledUpdate(BaseModel):
    enabled: bool


class NewsUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    full_summary: str | None = None
    category: str | None = None
    importance: int | None = None


class AdminToggle(BaseModel):
    is_admin: bool


class CategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class SettingsUpdate(BaseModel):
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    proxy_url: str | None = None
