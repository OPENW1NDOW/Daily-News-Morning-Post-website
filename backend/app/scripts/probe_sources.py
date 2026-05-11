"""
探测所有 RSS 源是否可达。
用法：cd backend && python -m app.scripts.probe_sources [--proxy]
  --proxy   强制所有源走代理（用于测试海外源）
"""
import asyncio
import sys
import pathlib
import yaml

# 允许直接运行时找到 app 包
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from app.utils.http import make_async_client
from app.utils.logger import get_logger
from app.config import settings

logger = get_logger("probe_sources")

TIMEOUT = 12.0


def _resolve_url(url: str) -> str:
    """替换 URL 中的 ${RSSHUB_BASE_URL} 占位符。"""
    return url.replace("${RSSHUB_BASE_URL}", settings.rsshub_base_url)


async def probe_one(key: str, name: str, url: str, use_proxy: bool, semaphore: asyncio.Semaphore) -> dict:
    async with semaphore:
        try:
            async with make_async_client(use_proxy=use_proxy, timeout=TIMEOUT) as client:
                resp = await client.get(_resolve_url(url))
                status = resp.status_code
                ok = status < 400
                return {"key": key, "name": name, "ok": ok, "status": status, "error": None}
        except Exception as e:
            return {"key": key, "name": name, "ok": False, "status": None, "error": str(e)[:80]}


async def main(force_proxy: bool = False):
    # 从 backend/ 目录下的 config/sources.yaml 读取
    # __file__ = backend/app/scripts/probe_sources.py → parents[2] = backend/
    cfg_path = pathlib.Path(__file__).resolve().parents[2] / "config" / "sources.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    sources = cfg["sources"]

    semaphore = asyncio.Semaphore(10)
    tasks = [
        probe_one(
            s["key"], s["name"], s["url"],
            use_proxy=force_proxy or s.get("use_proxy", False),
            semaphore=semaphore,
        )
        for s in sources if s.get("enabled", True)
    ]
    results = await asyncio.gather(*tasks)

    ok_list = [r for r in results if r["ok"]]
    fail_list = [r for r in results if not r["ok"]]

    print(f"\n{'='*60}")
    print(f"探测完成：{len(ok_list)} 成功 / {len(fail_list)} 失败 / 共 {len(results)} 个源")
    print(f"{'='*60}")

    if ok_list:
        print("\n[OK] 成功：")
        for r in ok_list:
            print(f"  [{r['status']}] {r['name']:20s}  {r['key']}")

    if fail_list:
        print("\n[FAIL] 失败：")
        for r in fail_list:
            err = r["error"] or f"HTTP {r['status']}"
            print(f"  {r['name']:20s}  {r['key']:20s}  {err}")

    print()
    return len(fail_list) == 0


if __name__ == "__main__":
    force_proxy = "--proxy" in sys.argv
    success = asyncio.run(main(force_proxy=force_proxy))
    sys.exit(0 if success else 1)
