import pathlib
import yaml
from sqlalchemy.orm import Session
from ..models import Source
from ..utils.logger import get_logger

logger = get_logger(__name__)

_SOURCES_PATH = pathlib.Path(__file__).parent.parent.parent / "config" / "sources.yaml"


def sync_sources(db: Session) -> None:
    """将 sources.yaml 同步到数据库 sources 表。"""
    cfg = yaml.safe_load(_SOURCES_PATH.read_text(encoding="utf-8"))
    for item in cfg.get("sources", []):
        src = db.query(Source).filter_by(key=item["key"]).first()
        if src is None:
            src = Source(key=item["key"])
            db.add(src)
        src.name = item["name"]
        src.url = item["url"]
        src.use_proxy = item.get("use_proxy", False)
        src.enabled = item.get("enabled", True)
    db.commit()
    logger.info(f"sources 同步完成，共 {len(cfg.get('sources', []))} 个源")
