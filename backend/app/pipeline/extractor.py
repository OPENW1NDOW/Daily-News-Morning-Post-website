import trafilatura
from ..utils.http import make_client
from ..utils.logger import get_logger

logger = get_logger(__name__)


def extract_text(url: str, use_proxy: bool = False) -> str | None:
    """用 trafilatura 抓取并提取正文，失败返回 None。"""
    try:
        with make_client(use_proxy=use_proxy, timeout=10.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        logger.warning(f"抓取页面失败 {url}: {e}")
        return None

    text = trafilatura.extract(html, include_comments=False, include_tables=False)
    if not text:
        logger.debug(f"trafilatura 未提取到正文 {url}")
    return text


def batch_extract(db, use_proxy: bool = False) -> tuple[int, int]:
    """对 raw_articles 中缺 full_text 的条目批量补抓，返回 (成功数, 总数)。"""
    from ..models import RawArticle

    articles = db.query(RawArticle).filter(RawArticle.full_text.is_(None)).all()
    total = len(articles)
    success = 0
    for art in articles:
        text = extract_text(art.link, use_proxy=use_proxy)
        if text:
            art.full_text = text
            success += 1
        else:
            # 降级用 raw_summary
            art.full_text = art.raw_summary
    db.commit()
    logger.info(f"正文提取完成：{success}/{total} 条成功（其余降级用 raw_summary）")
    return success, total
