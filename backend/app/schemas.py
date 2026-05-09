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
