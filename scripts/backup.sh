#!/usr/bin/env bash
# 每日备份：mysqldump + 文件增量同步。
# 文件不在库里，所以 dump 只有几 MB，rsync 只传变化部分 —— 这是磁盘方案最实在的收益。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/backend/.env"
STAMP="$(date +%Y%m%d-%H%M)"

DB_NAME="$(grep -E '^MYSQL_DB=' "$ENV_FILE" | cut -d= -f2-)"
DATA_ROOT="$(grep -E '^DATA_ROOT=' "$ENV_FILE" | cut -d= -f2- | sed "s|~|$HOME|")"
DEST="${1:-$DATA_ROOT/backups}"

mkdir -p "$DEST"

echo "[1/2] 导出数据库…"
mysqldump --single-transaction --quick --default-character-set=utf8mb4 \
  -u root -p "$DB_NAME" | gzip > "$DEST/db-$STAMP.sql.gz"

echo "[2/2] 同步上传文件…"
rsync -a --delete "$DATA_ROOT/uploads/" "$DEST/uploads/"

# 只保留最近 30 份 dump
ls -1t "$DEST"/db-*.sql.gz 2>/dev/null | tail -n +31 | xargs -r rm -f

echo "✓ 备份完成：$DEST"
du -sh "$DEST" 2>/dev/null || true
