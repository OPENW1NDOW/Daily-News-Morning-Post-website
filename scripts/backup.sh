#!/usr/bin/env bash
# SQLite 每日备份脚本（跑在服务器宿主机，非容器内）
#
# 原理：backend 镜像（python:3.11-slim）没有 sqlite3 CLI，
# 故用容器内 python 的 sqlite3.backup API 生成一致性快照（WAL 模式下安全），
# 再 docker cp 到宿主机，保留最近 14 份。
#
# crontab 配置示例（每日 03:00）：
#   0 3 * * * /opt/news-website/scripts/backup.sh >> /var/log/news-backup.log 2>&1

CONTAINER="news-backend"
DB_PATH="/app/data/news.db"
CONTAINER_BACKUP_DIR="/app/data/backups"
HOST_BACKUP_DIR="/opt/news-website/backups"
KEEP=14

DATE="$(date +%Y-%m-%d_%H%M%S)"
BACKUP_NAME="news_${DATE}.db"

if ! docker exec "$CONTAINER" mkdir -p "$CONTAINER_BACKUP_DIR"; then
    echo "[backup] ERROR: 容器内创建备份目录失败（容器 ${CONTAINER} 是否在运行？）" >&2
    exit 1
fi

if ! docker exec "$CONTAINER" python -c "
import sqlite3
src = sqlite3.connect('${DB_PATH}')
dst = sqlite3.connect('${CONTAINER_BACKUP_DIR}/${BACKUP_NAME}')
with dst:
    src.backup(dst)
dst.close()
src.close()
"; then
    echo "[backup] ERROR: 数据库快照生成失败" >&2
    exit 1
fi

if ! mkdir -p "$HOST_BACKUP_DIR"; then
    echo "[backup] ERROR: 宿主机备份目录 ${HOST_BACKUP_DIR} 创建失败" >&2
    exit 1
fi

if ! docker cp "${CONTAINER}:${CONTAINER_BACKUP_DIR}/${BACKUP_NAME}" "${HOST_BACKUP_DIR}/${BACKUP_NAME}"; then
    echo "[backup] ERROR: docker cp 拷贝到宿主机失败" >&2
    exit 1
fi

# 快照已落盘宿主机，清掉容器内副本避免数据卷膨胀
docker exec "$CONTAINER" rm -f "${CONTAINER_BACKUP_DIR}/${BACKUP_NAME}"

# 只保留最近 KEEP 份
ls -1t "${HOST_BACKUP_DIR}"/news_*.db 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
    rm -f -- "$old"
done

echo "[backup] OK: ${HOST_BACKUP_DIR}/${BACKUP_NAME}"
