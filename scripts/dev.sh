#!/usr/bin/env bash
# 一键起前后端。Ctrl+C 同时退出两个进程。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ ! -f "$ROOT/backend/.env" ]; then
  echo "缺少 backend/.env，先跑：bash scripts/init_db.sh"
  exit 1
fi

if [ ! -d "$ROOT/backend/.venv" ]; then
  echo "首次运行，创建 venv 并安装依赖…"
  python3 -m venv "$ROOT/backend/.venv"
  "$ROOT/backend/.venv/bin/pip" install -q -r "$ROOT/backend/requirements.txt"
fi

if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "首次运行，安装前端依赖…"
  (cd "$ROOT/frontend" && npm install)
fi

cd "$ROOT/backend"
# 只监视 app 目录：默认会连 .venv 一起监视，pip 装个包就触发十几次热重载
.venv/bin/uvicorn app.main:app --reload --reload-dir app --port 8000 &
BACK=$!

cd "$ROOT/frontend"
npm run dev -- --port 5173 &
FRONT=$!

cleanup() {
  kill "$BACK" "$FRONT" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo
echo "后端 http://127.0.0.1:8000/docs"
echo "前端 http://127.0.0.1:5173"
echo "Ctrl+C 退出"
wait
