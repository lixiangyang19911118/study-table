# 后端 · FastAPI 应用

小学学习工作台的后端。家长布置任务、孩子提交拍照、家长审核发星，错题按 1/2/4/7 天间隔自动回流。

MySQL 8.0 + SQLAlchemy 2.0 同步 ORM + Alembic，单进程 uvicorn。**单机自用**，没有 Redis、没有 Celery、没有 OSS SDK。

> 本章所有路径均相对于 `backend/`，例如 `app/main.py` 即 `backend/app/main.py`。

---

## 跑起来

```bash
# 依赖（首次）
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 建表
.venv/bin/alembic upgrade head

# 起服务
.venv/bin/python -m app.main          # 或 IDE 里点绿三角
```

- 接口文档 <http://127.0.0.1:8000/docs>
- 健康检查 <http://127.0.0.1:8000/api/v1/health>

建库和 `.env` 由根目录的 `scripts/init_db.sh` 一次生成，它会问 MySQL root 密码。**没有 `.env` 也能启动**，用的是 `config.py` 里的默认值，但连不上库。

命令行只能用 `python -m app.main`，不要用 `python app/main.py` —— 后者的 `sys.path[0]` 会变成 `app/`，`import app.xxx` 全部失败。

---

## 分层

### 分层的目的

不是为了让目录整齐，而是为了**改一处只影响一处**。四条硬要求：

| 将来的变化 | 只应该改这里 |
|---|---|
| 文件从本地磁盘换成 OSS | `app/integrations/` |
| 加字段、改索引 | `app/models/` + 一版迁移 |
| 接口协议变化 | `app/api/v1/` + `app/schemas/` |
| 连接串、超时、上传上限 | `app/core/config.py` |

如果某次改动被迫同时打开四个目录，说明分层被穿透了。

### 五层 + 两条旁路

```
┌──────────────────────────────────────────────────────────┐
│  接入层   app/main.py   app/api/v1/                       │
│           HTTP、参数校验、状态码、鉴权                     │
├──────────────────────────────────────────────────────────┤
│  契约层   app/models/          app/schemas/               │
│           ORM 表映射            请求/响应模型              │
├──────────────────────────────────────────────────────────┤
│  业务层   app/services/                                   │
│           状态机、事务边界、跨表编排                       │
├──────────────────────────────────────────────────────────┤
│  基础层   app/core/                                       │
│           配置、连接池、口令散列、JWT、本地日期            │
├──────────────────────────────────────────────────────────┤
│  适配层   app/integrations/                               │
│           磁盘存储；将来的 LLM / OCR                       │
└──────────────────────────────────────────────────────────┘

旁路 A  app/tasks/   定时任务，不处理 HTTP，自己开关 Session
旁路 B  alembic/     表结构演进，不在运行时被 import
```

### 依赖方向

```
             main.py
           ╱    │    ╲
        api     │    tasks
         │ ╲    │    ╱
         │  ╲   ▼   ╱
         │   services
         │      │
         ▼      ▼
 integrations   models
         ╲      ╱
          ▼    ▼
           core
```

四条规则，没有例外：

1. **`core/` 是最底层**，只 import 第三方库，不 import 项目内任何模块
2. **`models/` 不 import `api/` 和 `tasks/`**，表结构不应该知道谁在调用它
3. **`integrations/` 不 import `app.models`** —— 它一旦认识数据库模型，就再也换不掉了
4. **`api/` 和 `tasks/` 平级，互不 import**，两者都要用的逻辑往下沉到 `services/`

第五条是 M2 补的，也是实际最容易被违反的一条：**`api/` 不许直接改 `status` 这类状态字段**，一律调 `services`。详见下面 `app/services/` 一节。

### 一次请求怎么走

以 `GET /api/v1/files/12` 为例，每一跳都落在不同目录：

| 步 | 发生什么 | 落在哪 |
|---|---|---|
| 1 | uvicorn 收到 TCP 连接 | — |
| 2 | 命中 `/api/v1` 前缀，交给汇总路由 | `app/main.py` 的 `include_router` |
| 3 | 按子路由分发给具体函数 | `app/api/v1/router.py` |
| 4 | 函数签名 `db: Session = Depends(get_db)` 触发依赖注入，开一个 Session，请求结束自动关闭 | `app/core/db.py` |
| 5 | `db.get(FileObject, 12)` 走 ORM 映射 → PyMySQL → MySQL | `app/models/entities.py` |
| 6 | 拿到 `rel_path` 后拼绝对路径，并校验没有越界 | `app/integrations/storage.py` |
| 7 | `FileResponse` 流式发出，40MB 教材不进 Python 内存 | — |

这条链路的实用价值是**报错能定位**：文件返回 404 就去第 5 步看数据库那行在不在；返回 403 路径越界就去第 6 步；返回 410 说明库里有记录但磁盘文件没了。

---

## 逐目录说明

### `app/main.py`

应用装配，全文 70 行，只做四件事：建数据目录、起调度器、挂 CORS、挂路由。

`lifespan` 里启动调度器、关闭时停掉，这是 APScheduler 和 FastAPI 的接入点。

**不放**：任何业务逻辑、任何 SQL、任何 `if/else` 判断。

末尾的 `if __name__ == "__main__"` 是给 IDE 绿三角和 `python -m app.main` 用的：

```python
uvicorn.run(
    "app.main:app",        # 必须传字符串，传 app 对象 reload 不生效
    port=8000,
    reload=True,
    reload_dirs=["app"],   # 只监视 app，否则 .venv 会被监视
)
```

CORS 只放行 `5173` 两个来源，`allow_credentials=True` 是为 Cookie 鉴权准备的。上云后改成同源反代，这段可以整块删掉。

### `app/core/`

原则：**所有和环境有关的东西只在这里出现一次**。

| 文件 | 职责 | 关键点 |
|---|---|---|
| `config.py` | 读 `.env`，唯一的配置来源 | `database_url`、`upload_dir` 是从字段拼出来的 property，别处不要再拼一遍；密码过 `quote_plus`，否则含 `@`、`#` 时连接串解析错位 |
| `db.py` | engine + SessionLocal + `get_db` 依赖 | 同步 Session，刻意不用 async ORM；`pool_recycle=3600` 要小于 MySQL 的 `wait_timeout`，否则空闲久了报 `MySQL server has gone away` |
| `security.py` | scrypt 口令散列 + JWT 签发校验 | 用标准库 `hashlib.scrypt`，不引 passlib —— 它和新版 bcrypt 长期不兼容 |
| `clock.py` | 本地时区的「现在 / 今天」 | 库里存 UTC，但 `task_date` 记的是「哪一天」。晚上 8 点之后布置的任务若用 `date.today()` 会落到第二天 |

**不放**：业务规则。`core` 被所有层依赖，它一旦 import 上层就会立刻循环依赖。

两个必须知道的细节：

- `settings` 是模块级单例，`.env` **只在进程启动时读一次**。改完 `.env` 必须重启，热重载不会重新读
- 口令不存明文也不存 md5，`hash_secret` 输出 `scrypt$N$r$p$salt$hash`，参数跟着散列一起存，将来调高强度不用洗数据

### `app/models/`

数据库表结构的**唯一来源**。

| 文件 | 内容 |
|---|---|
| `base.py` | `Base`、`TimestampMixin`、`utcnow()` |
| `entities.py` | 15 张表，一张表一个类 |
| `__init__.py` | 统一导出，`alembic/env.py` 靠 `from app.models import Base` 收齐 metadata |

**放**：`mapped_column`、索引、唯一约束、外键、`comment=`。

**不放**：查询语句、业务判断、密码散列。模型只管"数据长什么样"，不管"数据怎么用"。

时间约定：**统一存 UTC 的 naive datetime**，展示层再转 `Asia/Shanghai`。混着存本地时间，跨时区查询一定会出错。

改表的正确姿势：

```bash
# 改 entities.py，然后
.venv/bin/alembic revision --autogenerate -m "add xxx"
.venv/bin/alembic upgrade head
```

不要直接 `ALTER TABLE`。直连数据库改完，下次重建库时那个字段就没了。

字段注释也写在模型里（`comment=` 参数），当前覆盖率 **15 张表 / 139 个字段，100%**。新加字段漏了 `comment=` 就会破，补回来要多写一版迁移。

### `app/schemas/`

Pydantic 请求/响应模型。

| 文件 | 内容 |
|---|---|
| `auth.py` | 登录、账号、孩子档案的入参与出参 |
| `task.py` | 任务的布置/修改/提交/退回，以及 `TaskBrief` / `TaskDetail` 两种出参 |

约定：**ORM 对象不直接返回**，一律经 schema 转换。这不是洁癖，是防止字段泄漏的唯一手段。

列表用 `TaskBrief`（不带照片和审核流水，只带 `shot_count`），详情用 `TaskDetail`。列表页每条都塞全量照片，二十条任务就是二十次多余查询。

时间字段带一个 `field_serializer` 输出 `+00:00`。库里是 UTC naive，直接吐出去会被 JS 的 `new Date()` 当本地时间，晚上八点之后能差出一天。

### `app/api/v1/`

HTTP 接入层。

| 文件 | 职责 |
|---|---|
| `router.py` | 七行汇总，只做 `include_router` |
| `health.py` | `/health` 与 `/meta`。设计原则是"库连不上也要能报出原因"，所以它吞异常并如实返回，绝不抛 500 |
| `auth.py` | 登录、登出、`/me`。JWT 只写 HttpOnly Cookie，响应体里没有 token |
| `children.py` | 孩子档案增删改查 |
| `files.py` | 上传与读取 |
| `tasks.py` | 13 个任务接口，覆盖布置到发星全链路 |
| `deps.py` | `get_current_account` / `owned_child` / `owned_task`，身份只从这里来 |

**放**：参数校验、状态码、权限判断、调用下层。

**不放**：复杂 SQL、文件字节处理、跨表业务编排、**任何 `task.status = "xxx"` 的直接赋值**。

`files.py` 里有一处顺序值得记住：**先落盘，再判断真实大小，超限就删掉再报 413**。原因是 `UploadFile.size` 不可靠（分块传输时可能是 `None`），只有写完才知道真实字节数，所以必须有回收动作，否则会留下孤儿文件。

`biz_type` 用白名单（`{"book","shot","avatar"}`）而不是自由字符串，因为它会直接参与磁盘路径拼接。

M1 起两个文件接口都要登录，`child_id` 改为从当前账号推导。M0 时它是从表单直接收的，任何人传别人的 `child_id` 就能读到别人家的照片。

### `app/services/`

业务编排层。M2 只有一个文件 `task_service.py`，但它是整个后端最该守住的地方。

**所有 `task.status` 变更只能走这里。** 路由层直接赋值一行代码就能绕过计时结算、审核流水和星星流水，而且不会报错——出问题时表现为"这孩子星星少了一颗"，极难定位。

#### 状态机：5 态 6 边

```
todo --start--> doing --submit--> submitted --approve--> done（终态）
                   ↑                  │
                   │                  ├--reject--> rejected --restart--┐
                   └----withdraw------┘                                │
                   └──────────────────────────────────────────────────┘
```

| 边 | 触发 | 前置条件 | 副作用 |
|---|---|---|---|
| `start` | 孩子 | todo | `started_at = now` |
| `submit` | 孩子 | doing，且照片或说明至少一项 | `spent_sec += now - started_at`，记 `submit_note` |
| `approve` | 家长 | submitted | 写 `task_review`，写 `star_ledger +stars` |
| `reject` | 家长 | submitted，原因非空 | 写 `task_review`，清空 `submit_note` |
| `withdraw` | 孩子 | submitted | `started_at` 重置，避免二次提交重复计时 |
| `restart` | 孩子 | rejected | `started_at` 重置 |

`done` 没有出边。M2 明确不做「撤销审核」——它会让孩子看到星星变少，解释成本高于收益。误审只能改库。

#### 三条不容易想到的实现细节

**1. 用条件更新挡并发，不做先查后改。**

```python
update(Task).where(Task.id == id, Task.status.in_(("submitted",)), ...)
if db.execute(stmt).rowcount == 0:
    raise TaskStateError("任务当前是「已完成」，不能执行这个操作")
```

家长连点两下审核、手机和电脑同时点，只有一次 `rowcount == 1`，另一次 409。先 `db.get` 再判断 `if status == "submitted"` 的做法在中间留了窗口，结果是发两份星星。

**2. 状态变更和流水写在同一个事务里。** `_transition()` 只 `execute` 不 `commit`，调用方把 `TaskReview`、`StarLedger` 加进去后统一提交。中途失败则一起回滚，不会出现"任务完成了但星星没到账"。

**3. 逾期不是一种状态，是算出来的。**

```
今日   task_date == 今天 且 status in (todo, doing, rejected)
补做   task_date < 今天 且 status in (todo, doing, rejected)
待审核 status == submitted（不限日期）
已完成 status == done 且 task_date == 今天
```

好处：不依赖定时任务。电脑关机三天再打开，补做区依然是对的；如果靠 23:59 跑批标记逾期，进程没跑那天就漏了一批。

注意「待审核」不分日期：昨天交了家长没审，球在家长那边，不该算孩子没完成。

#### 为什么退回后要求「有新东西」

`submit` 会查这个任务最后一次 `reject` 的时间，要求那之后有新照片，或有一句新说明。否则孩子原样再点一次提交就能绕过退回，退回就变成了一个纯装饰的按钮。

这也是 `reject` 要清空 `submit_note` 的原因：清空之后，「有说明」就等于「新说明」，判断只需要一行。

### `app/integrations/`

外部依赖的适配层，目前只有 `storage.py`。

```
Storage (ABC)          save / path / delete
   └── LocalStorage    唯一实现，写本地磁盘
get_storage()          单例入口
```

换 OSS 时新增一个 `OSSStorage` 实现同样三个方法，业务代码一行不改。这是它存在的**唯一**目的。

红线：**不要在这里 `import app.models`**。

`path()` 里的越界校验不是可选优化：

```python
p = (self.root / rel_path).resolve()
if p != self.root and self.root not in p.parents:
    raise PermissionError("路径越界")
```

没有它，一个 `rel_path = "../../etc/passwd"` 就能读走任意文件。`resolve()` 必须在拼接**之后**调用，否则 `..` 不会被折叠。

`save()` 是一边读一边写、同时算 sha256，所以 40MB 教材不会整个进内存。磁盘布局按月分目录（`shots/2026/11/`），避免单目录堆到几万个文件。

### `app/tasks/`

定时任务。**先注意名字歧义**：这里的 task 指"后台任务"，不是 `models.Task`（学习任务）。

| 文件 | 职责 |
|---|---|
| `scheduler.py` | APScheduler 启停，两个 cron：00:10 错题到期扫描、23:55 打卡结算 |
| `jobs.py` | 两个函数本体 |

**为什么用 APScheduler 而不是 Celery**：只有一个 uvicorn 进程，没有跨进程分发需求，省掉 Redis 和一个常驻 worker。

这个方案成立的前提是**单进程**。`uvicorn --workers N` 会让每个进程各跑一份，错题被重复生成。三个条件满足任一就该换 Celery：① 起多 worker；② 单次任务超过一分钟；③ 开始对外提供服务。

`jobs.py` 的两条铁律：

1. **任务本身必须幂等**，不能依赖"调度器只跑一次"。`scan_due_mistakes` 靠 `task` 表的 `uk_task_source` 唯一约束兜底，重复执行也只会有一行
2. **每个函数自己开关 Session**（`with SessionLocal() as db`），这样能被命令行手动补跑，不必先起服务

### `alembic/`

表结构演进。`0001` 建 15 张表，`0002` 补中文注释，`0003` 给 `account` 加登录名，`0004` 给 `task` 加 `submit_note`。

`env.py` 里三件事值得知道：

- `sys.path.insert(0, ...)` 把 backend 根目录塞进 `sys.path`，否则迁移时 import 不到 `app`
- `url` 优先读环境变量 `ALEMBIC_URL`，其次才是 `.env`。这个设计让"不连库生成 DDL"成为可能：
  ```bash
  ALEMBIC_URL="mysql+pymysql://u:p@h/db" .venv/bin/alembic upgrade head --sql
  ```
- `url.replace("%", "%%")`：密码含 `%` 时 Alembic 的 configparser 会把它当插值符号，不转义直接报错

三个已知限制，都踩过：

- **autogenerate 不检测 MySQL 注释变化**，表注释和列注释都必须手写迁移
- **`MODIFY COLUMN` 会重写整列定义**。只写 `MODIFY COLUMN x int COMMENT '...'` 会抹掉 `ON UPDATE CURRENT_TIMESTAMP`、`AUTO_INCREMENT`、`DEFAULT`。正确做法是从 `SHOW CREATE TABLE` 原样取出列定义，再追加 `COMMENT`（0002 就是脚本生成的，不是手抄）
- **表注释必须单独一条** `ALTER TABLE ... COMMENT='...'`。写进 `MODIFY COLUMN` 列表里，MySQL 会把它当成上一列的 `COMMENT` 子句，报 1064

### `tests/`

32 条，约 2 秒跑完。

| 文件 | 内容 |
|---|---|
| `conftest.py` | `account_factory`：唯一用户名建账号，用例结束删账号（级联删孩子） |
| `test_smoke.py` | 健康检查、404、不依赖库里的数据 |
| `test_auth.py` | 登录成功/失败、未登录 401、跨账号 403 |
| `test_task_flow.py` | 状态机 6 条边 + 6 条不该通过的路径 + 补做区口径 |

```bash
.venv/bin/python -m pytest tests -q
```

两条测试环境的取舍：

- **不建独立测试库。** `study` 账号只有 `study_table` 的权限，建不了库。改用唯一用户名隔离 + 用例后 CASCADE 清理，比为此去要 root 权限划算。
- **不用 `with TestClient(app)`。** 那会触发 lifespan，每条用例起停一次 APScheduler，用例一多就慢且偶发报错。

`test_missing_file_never_200` 用了 `TestClient(app, raise_server_exceptions=False)`：不关掉的话未捕获异常会直接抛进测试，测的就变成"代码里有没有 try"，而不是"接口怎么响应"。

照片相关的用例直接建 `file_object` 记录，不走 `/files` 上传：测试不关心落盘，也不想往磁盘扔垃圾。清理时要先删 `task_shot` 再删 `file_object`——`task_shot.file_id` 是 `ON DELETE RESTRICT`，顺序反了会报外键错误。

---

## 数据目录

文件不放在仓库里，也不进数据库。位置由 `.env` 的 `DATA_ROOT` 决定，默认 `~/study_table_data/`：

```
uploads/books/                   教材 PDF
uploads/shots/2026/11/           作业与错题照片，按月分目录
uploads/avatars/2026/11/         头像
backups/                         mysqldump + 文件快照
```

库里 `file_object` 只存 `rel_path`（如 `books/a3f9c1.pdf`），**不存 BLOB、不存 base64**。因为文件在库外，`mysqldump` 只有几 MB，备份和恢复都是秒级。

---

## 新增一个接口的标准动作

以"孩子端获取今日任务列表"为例：

1. 看 `models/entities.py` 字段够不够，不够就加列
2. `alembic revision --autogenerate -m "..."`，**人工检查一遍生成的迁移**（autogenerate 会漏注释、有时漏 `server_default`）
3. `.venv/bin/alembic upgrade head`
4. `schemas/task.py` 定义 `TaskOut`
5. `api/v1/tasks.py` 写路由，签名里 `Depends(get_db)`
6. `api/v1/router.py` 加一行 `include_router`
7. `tests/` 补一条，至少覆盖空列表和正常返回
8. 前端 `src/api/` 加对应函数

**如果第 5 步超过 40 行，说明该抽 `services/` 了。**

---

## 尚未建立的两个目录

写清楚，免得后来者到处找。

### `app/services/` —— 业务编排层，M2 起引入

M0 业务还薄，`api/` 直接调 `models/` 够用。M2 会出现"布置任务要同时写 task + 提醒 + 流水"这种跨表动作，那时必须下沉，否则 `api/` 和 `tasks/jobs.py` 会各写一份，然后慢慢漂移。

判据很简单：**同一段业务逻辑被 `api/` 和 `tasks/` 都要用到时，就该抽。**

### `app/utils/` —— 不建

叫 utils 的目录最后都会变成垃圾桶。真需要公共函数时按归属放：基础设施进 `core/`，业务进 `services/`。

---

## 开发约定

1. **依赖方向不能倒**：`core ← models ← api`，`integrations` 不认识 `models`
2. **表结构只从 `models/` 改**，且必须走迁移，不直接 `ALTER` 数据库
3. **新字段必须带 `comment=`**，覆盖率破了 100% 就要多写一版迁移补回来
4. **返回给前端的对象必须过 schemas**，不直接吐 ORM 对象
5. **定时任务必须幂等**，不能假设"只会跑一次"
6. **`api/` 里不做文件字节处理**，交给 `integrations/storage.py`
7. **`settings` 只在启动时读一次**，改 `.env` 必须重启

---

## 踩过的坑

| 现象 | 原因 | 解法 |
|---|---|---|
| pip 装个包，后端重启十几次 | `--reload` 默认监视整个 backend 目录 | `--reload-dir app` |
| 建表报 1064 语法错 | `range` 是 MySQL 保留字 | 列名用 `range_max` |
| 改完 `.env` 没生效 | `settings` 是模块级单例，只读一次 | 重启进程 |
| `python app/main.py` 报 import 错误 | `sys.path[0]` 变成 `app/` | 用 `python -m app.main` |
| 迁移报 `Invalid %` | 密码含 `%`，configparser 当插值符 | `url.replace("%", "%%")` |
| 表注释丢失 `ON UPDATE` | `MODIFY COLUMN` 重写整列 | 从 `SHOW CREATE TABLE` 取原定义 |
| 建了 `'study'@'127.0.0.1'` 却连不上 | `skip_name_resolve` 关闭时 127.0.0.1 反解成 localhost，是两个账号 | 两个 host 都建 |
| 上传后磁盘有孤儿文件 | `UploadFile.size` 可能是 `None` | 落盘后校验真实大小并回收 |

还有一个**还没踩但一定会踩**的：`<img>` 和 PDF 的 `<iframe>` 带不上 `Authorization` 头。M1 加鉴权时，JWT 必须同时写进 HttpOnly Cookie，否则图片和教材全部 401。

---

## 后端进度

| 阶段 | 后端内容 | 状态 |
|---|---|---|
| M0 | 工程骨架、15 张表 + 迁移、存储适配、调度器、健康检查 | 完成 |
| M1 | 登录、账号、孩子档案、JWT 进 Cookie | 未开始 |
| M2 | 任务主链路接口：布置 → 提交 → 审核 → 发星 | 未开始 |
| M3 | 错题本 + 口算出题与判分（必须放在后端） | 未开始 |
| M4 | 教材上传与个人设置 | 未开始 |
| M5 | AI 助手 SSE + 拍照识别，含超时与每日次数上限 | 未开始 |
| M6 | 备份脚本、恢复演练 | 未开始 |
