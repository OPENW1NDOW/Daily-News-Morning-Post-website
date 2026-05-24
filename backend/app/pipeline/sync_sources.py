import pathlib
import yaml
from sqlalchemy.orm import Session
from ..models import Source
from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

_SOURCES_PATH = pathlib.Path(__file__).parent.parent.parent / "config" / "sources.yaml"


def _resolve_url(url: str) -> str:
    """替换 URL 中的 ${RSSHUB_BASE_URL} 占位符。"""
    return url.replace("${RSSHUB_BASE_URL}", settings.rsshub_base_url)


def sync_sources(db: Session) -> None:
    """将 sources.yaml 同步到数据库 sources 表。
    新源：按 YAML 初始化所有字段。
    已有源：只更新 name 和 url，保留用户在 admin 面板设置的 enabled/use_proxy。
    """
    cfg = yaml.safe_load(_SOURCES_PATH.read_text(encoding="utf-8"))
    for item in cfg.get("sources", []):
        src = db.query(Source).filter_by(key=item["key"]).first()
        if src is None:
            src = Source(key=item["key"])
            db.add(src)
            src.use_proxy = item.get("use_proxy", False)
            src.enabled = item.get("enabled", True)
        src.name = item["name"]
        src.url = _resolve_url(item["url"])
    db.commit()
    logger.info(f"sources 同步完成，共 {len(cfg.get('sources', []))} 个源")
