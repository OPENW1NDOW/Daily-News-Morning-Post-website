"""RSSHub 实例生命周期管理：自动检测、启动、停止。"""
import atexit
import os
import signal
import subprocess
import time
from urllib.parse import urlparse

import httpx

from .config import settings
from .utils.logger import get_logger

logger = get_logger(__name__)

_process: subprocess.Popen | None = None


def _is_alive() -> bool:
    """检测 RSSHub 是否已在线。"""
    try:
        resp = httpx.get(settings.rsshub_base_url, timeout=3, follow_redirects=True)
        return resp.status_code < 500
    except Exception:
        return False


def _resolve_rsshub_dir() -> str:
    """解析 RSSHub 项目目录路径。"""
    if settings.rsshub_dir:
        return settings.rsshub_dir
    # 默认：与项目同级的 rsshub 目录（backend/../../rsshub）
    from pathlib import Path
    return str(Path(__file__).resolve().parents[3] / "rsshub")


def _cleanup():
    """退出时清理 RSSHub 进程树（包括所有子进程）。"""
    global _process
    if _process and _process.poll() is None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(_process.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            _process.terminate()
            try:
                _process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _process.kill()


def _kill_orphans_on_port(port: int):
    """清理占用指定端口的孤儿进程（Windows）。"""
    if os.name != "nt":
        return
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                if pid.isdigit() and int(pid) != os.getpid():
                    logger.info(f"清理端口 {port} 上的孤儿进程 PID={pid}")
                    subprocess.run(
                        ["taskkill", "/T", "/F", "/PID", pid],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
    except Exception as e:
        logger.debug(f"清理孤儿进程时出错: {e}")


def start():
    """启动 RSSHub 实例。如果已在线则跳过。"""
    global _process

    if _is_alive():
        logger.info(f"RSSHub 已在运行: {settings.rsshub_base_url}")
        return

    if not settings.rsshub_auto_start:
        logger.warning("RSSHub 未运行且 RSSHUB_AUTO_START=false，跳过自动启动")
        return

    # 先清理可能残留的孤儿 node 进程
    parsed = urlparse(settings.rsshub_base_url)
    port = parsed.port or 1200
    _kill_orphans_on_port(port)

    rsshub_dir = _resolve_rsshub_dir()
    logger.info(f"正在启动 RSSHub (目录: {rsshub_dir})...")

    try:
        cmd = ["npm.cmd", "run", "dev"] if os.name == "nt" else ["npm", "run", "dev"]
        _process = subprocess.Popen(
            cmd,
            cwd=rsshub_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        logger.error("npm 未找到，请确认 Node.js 已安装")
        return
    except Exception as e:
        logger.error(f"启动 RSSHub 失败: {e}")
        return

    # 等待就绪
    host = parsed.hostname or "localhost"
    for i in range(60):  # 最多 120 秒
        time.sleep(2)
        if _is_alive():
            logger.info(f"RSSHub 已就绪 ({host}:{port})")
            # 注册清理钩子
            atexit.register(_cleanup)
            if os.name != "nt":
                signal.signal(signal.SIGTERM, lambda s, f: (_cleanup(), exit(0)))
            return
        if _process.poll() is not None:
            logger.error(f"RSSHub 进程已退出 (exit code: {_process.returncode})")
            _process = None
            return

    logger.warning("RSSHub 启动超时（120秒），部分 RSSHub 源可能不可用")


def stop():
    """手动停止 RSSHub。"""
    _cleanup()
