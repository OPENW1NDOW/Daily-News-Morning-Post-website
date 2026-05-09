from datetime import datetime, date
from sqlalchemy import (
    Integer, String, Boolean, DateTime, Date, Text, JSON, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    use_proxy: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(String, default="unknown")

    raw_articles: Mapped[list["RawArticle"]] = relationship(back_populates="source")


class RawArticle(Base):
    __tablename__ = "raw_articles"
    __table_args__ = (UniqueConstraint("source_id", "guid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("sources.id"), nullable=False)
    guid: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    link: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    importance: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source: Mapped["Source"] = relationship(back_populates="raw_articles")


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    importance: Mapped[int] = mapped_column(Integer, default=50)
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    viewpoints: Mapped[list | None] = mapped_column(JSON, nullable=True)
    background: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_links: Mapped[list | None] = mapped_column(JSON, nullable=True)
    raw_article_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("raw_articles.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    favorite: Mapped["Favorite | None"] = relationship(back_populates="news_item", uselist=False)


class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    news_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("news_items.id"), unique=True, nullable=False)
    favorited_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    news_item: Mapped["NewsItem"] = relationship(back_populates="favorite")
