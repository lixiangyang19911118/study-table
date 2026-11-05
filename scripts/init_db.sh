#!/usr/bin/env bash
# 一次性初始化：建库、建应用账号、生成 .env。只需跑一次。
# 用法：bash scripts/init_db.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/backend/.env"
DB_NAME="study_table"
DB_USER="study"

if [ -f "$ENV_FILE" ]; then
  echo "backend/.env 已存在，跳过生成。若要重来请先删除它。"
else
  APP_PW="$(python3 -c 'import secrets,string;print("".join(secrets.choice(string.ascii_letters+string.digits) for _ in range(24)))')"
  SECRET="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')"
  cp "$ROOT/backend/.env.example" "$ENV_FILE"
  python3 - "$ENV_FILE" "$APP_PW" "$SECRET" "$DB_NAME" "$DB_USER" <<'PY'
import re, sys, pathlib
p = pathlib.Path(sys.argv[1]); pw, sk, db, user = sys.argv[2:6]
text = p.read_text(encoding="utf-8")

# 按整行替换，不依赖原来的占位值：.env.example 被改过也能正确落盘
def setkv(text, key, value):
    line = f"{key}={value}"
    if re.search(rf"^{key}=.*$", text, flags=re.M):
        return re.sub(rf"^{key}=.*$", line, text, count=1, flags=re.M)
    return text.rstrip("\n") + "\n" + line + "\n"

text = setkv(text, "MYSQL_USER", user)
text = setkv(text, "MYSQL_DB", db)
text = setkv(text, "MYSQL_PASSWORD", pw)
text = setkv(text, "SECRET_KEY", sk)
p.write_text(text, encoding="utf-8")
PY
  echo "已生成 backend/.env（随机密码与密钥）"
fi

# 从 .env 里读回刚生成（或已存在）的密码
APP_PW="$(grep -E '^MYSQL_PASSWORD=' "$ENV_FILE" | head -1 | cut -d= -f2-)"

echo
echo "接下来需要 MySQL 的 root 密码来建库和建应用账号。"
read -rs -p "MySQL root 密码: " ROOT_PW
echo

mysql -u root -p"$ROOT_PW" <<SQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${APP_PW}';
CREATE USER IF NOT EXISTS '${DB_USER}'@'127.0.0.1' IDENTIFIED BY '${APP_PW}';
ALTER USER '${DB_USER}'@'localhost' IDENTIFIED BY '${APP_PW}';
ALTER USER '${DB_USER}'@'127.0.0.1' IDENTIFIED BY '${APP_PW}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL

echo "✓ 库 ${DB_NAME} 与账号 ${DB_USER} 就绪"
echo "下一步：cd backend && .venv/bin/alembic upgrade head"
