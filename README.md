# 学习工作台 · M0 骨架

Vue 3 + FastAPI + MySQL 8.0，单机自用。技术方案见 `../outputs/学习工作台-技术方案评估-v1.1.html`。

## 四步跑起来

```bash
# 1. 建库、建应用账号、生成 .env（只需一次，会问 MySQL root 密码）
bash scripts/init_db.sh

# 2. 建表
cd backend && .venv/bin/alembic upgrade head && cd ..

# 3. 起前后端
bash scripts/dev.sh
```

- 前端 http://127.0.0.1:5173
- 接口文档 http://127.0.0.1:8000/docs
- 自检页就是首页，四项全绿说明环境通了

首次运行 `dev.sh` 会自动建 venv、装依赖、装 node_modules。

## 目录

```
backend/app
  core/         配置、同步 Session、口令与 JWT
  models/       15 张表
  api/v1/       health / files
  integrations/ storage（本地磁盘实现）
  tasks/        APScheduler 定时任务
backend/alembic  迁移，首版 0001_init_schema
frontend/src
  api/          请求封装，页面里不出现裸 axios
  views/kid     孩子端
  views/parent  家长端
scripts           init_db / dev / backup
```

后端的完整分层说明、依赖规则与目录职责见 `backend/README.md`，前端见 `frontend/README.md`。

## 已经落地的东西

- 15 张表 + 首版迁移，含 `uk_task_source` 唯一约束（错题生成任务的幂等兜底）
- 文件上传下载：边读边写、sha256、路径穿越防护、Range 读取
- 两个定时任务：00:10 错题到期扫描、23:55 打卡结算
- 健康检查：库、目录、调度器三项状态一眼可见
- 冒烟测试 6 条：`cd backend && .venv/bin/python -m pytest tests -q`

## 刻意没做的事

- 没有 Redis、没有 Celery、没有 OSS SDK —— 单进程单机用不上，见方案 v1.1 第 06 章
- 没有登录鉴权 —— M1 补。届时 `/files/{id}` 必须校验归属，**并且 token 要进 HttpOnly Cookie**，否则 `<img>` 和 PDF 的 iframe 会集体 401
- 没有业务接口 —— M2 起按里程碑补

## 数据目录

文件不在仓库里，在 `~/study_table_data/`（由 `.env` 的 `DATA_ROOT` 决定）：

```
uploads/books/    教材 PDF
uploads/shots/    作业与错题照片
backups/          mysqldump + 文件快照
```

**备份**：`bash scripts/backup.sh [目标目录]`，默认写回 `backups/`。因为文件不在库里，dump 只有几 MB。
建议再加一条 launchd/cron 每天跑一次，或者直接把它指向移动硬盘。
