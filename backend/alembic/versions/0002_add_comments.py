"""add table and column comments

给 15 张表补齐中文注释，共 138 个字段。

列定义不是手写的，而是从 SHOW CREATE TABLE 原样取出后追加 COMMENT，
这样 MODIFY COLUMN 不会丢掉 updated_at 的 ON UPDATE CURRENT_TIMESTAMP，
也不会改动类型、默认值、AUTO_INCREMENT。

表注释刻意单独成句：ALTER TABLE 里 COMMENT = '...' 紧跟 MODIFY COLUMN 时，
MySQL 会把它当成上一列的 COMMENT 子句，报 1064。

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-05 12:30:00
"""
import re
from collections.abc import Sequence

from alembic import op


revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 一条 ALTER 改一张表的全部列，比 138 条独立语句快得多
_UPGRADE = (
    """ALTER TABLE `account`
  MODIFY COLUMN `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  MODIFY COLUMN `phone` varchar(20) DEFAULT NULL COMMENT '登录手机号，可空（本机自用可先不填）',
  MODIFY COLUMN `password_hash` varchar(160) DEFAULT NULL COMMENT '登录口令的 scrypt 散列，不存明文',
  MODIFY COLUMN `nickname` varchar(32) NOT NULL COMMENT '家长昵称，孩子端用来称呼',
  MODIFY COLUMN `pin_hash` varchar(160) DEFAULT NULL COMMENT '家长端二次确认 PIN 的散列，审核发星前校验',
  MODIFY COLUMN `status` varchar(16) NOT NULL COMMENT '账号状态：active 正常 / disabled 停用',
  MODIFY COLUMN `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  MODIFY COLUMN `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间（UTC），MySQL 侧带 ON UPDATE';""",

    """ALTER TABLE `account` COMMENT = '家长账号：一个账号下挂一个或多个孩子';""",

    """ALTER TABLE `child`
  MODIFY COLUMN `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  MODIFY COLUMN `account_id` bigint NOT NULL COMMENT '所属家长账号，账号删除时级联删除孩子',
  MODIFY COLUMN `name` varchar(32) NOT NULL COMMENT '孩子昵称（不采集真实姓名）',
  MODIFY COLUMN `grade` int NOT NULL COMMENT '年级 1-6，用于内容与教材分级',
  MODIFY COLUMN `edition` varchar(32) NOT NULL COMMENT '默认教材版本，如人教版、苏教版',
  MODIFY COLUMN `avatar_file_id` bigint DEFAULT NULL COMMENT '头像文件 id，指向 file_object',
  MODIFY COLUMN `prefs` json DEFAULT NULL COMMENT '偏好设置 JSON：daily_cap 每日上限 / calc_range 口算范围 / daily_time 提醒时间 / 提醒开关',
  MODIFY COLUMN `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  MODIFY COLUMN `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间（UTC），MySQL 侧带 ON UPDATE';""",

    """ALTER TABLE `child` COMMENT = '孩子档案：年级与偏好设置，所有业务数据按 child_id 归属';""",

    """ALTER TABLE `calc_record`
  MODIFY COLUMN `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  MODIFY COLUMN `child_id` bigint NOT NULL COMMENT '归属孩子',
  MODIFY COLUMN `task_id` bigint DEFAULT NULL COMMENT '关联的口算任务 id；独立练习时为空',
  MODIFY COLUMN `range_max` int NOT NULL COMMENT '数值范围上限：10 / 20 / 100（列名避开保留字 range）',
  MODIFY COLUMN `total` int NOT NULL COMMENT '本轮总题数',
  MODIFY COLUMN `right_count` int NOT NULL COMMENT '答对题数',
  MODIFY COLUMN `seconds` int NOT NULL COMMENT '本轮用时（秒）',
  MODIFY COLUMN `types` json DEFAULT NULL COMMENT '题型数组：add/sub/fill_addend/fill_minuend/fill_sum/fill_diff/chain_add/chain_sub',
  MODIFY COLUMN `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  MODIFY COLUMN `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间（UTC），MySQL 侧带 ON UPDATE';""",

    """ALTER TABLE `calc_record` COMMENT = '口算记录：每完成一轮记一条，用于家长端看正确率与用时';""",

    """ALTER TABLE `chat_message`
  MODIFY COLUMN `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  MODIFY COLUMN `child_id` bigint NOT NULL COMMENT '归属孩子',
  MODIFY COLUMN `role` varchar(16) NOT NULL COMMENT '消息角色：user 孩子 / assistant 助手',
  MODIFY COLUMN `content` text NOT NULL COMMENT '消息正文',
  MODIFY COLUMN `tokens` int NOT NULL COMMENT '本条消耗的 token 数，用于成本控制',
  MODIFY COLUMN `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  MODIFY COLUMN `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间（UTC），MySQL 侧带 ON UPDATE';""",

    """ALTER TABLE `chat_message` COMMENT = '助手对话记录：按时间正序回放，用于构建上下文与用量统计';""",

    """ALTER TABLE `checkin`
  MODIFY COLUMN `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  MODIFY COLUMN `child_id` bigint NOT NULL COMMENT '归属孩子',
  MODIFY COLUMN `check_date` date NOT NULL COMMENT '打卡日期（本地日）；与 child_id 组成唯一键防重复',
  MODIFY COLUMN `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  MODIFY COLUMN `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间（UTC），MySQL 侧带 ON UPDATE';""",

    """ALTER TABLE `checkin` COMMENT = '每日打卡：一天一条，连续天数由日期序列实时计算';""",

    """ALTER TABLE `file_object`
  MODIFY COLUMN `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  MODIFY COLUMN `child_id` bigint DEFAULT NULL COMMENT '归属孩子，孩子删除后置空但保留文件记录',
  MODIFY COLUMN `biz_type` varchar(16) NOT NULL COMMENT '业务类型：book 教材 / shot 作业照片 / avatar 头像',
  MODIFY COLUMN `rel_path` varchar(255) NOT NULL COMMENT '相对 DATA_ROOT 的路径，如 uploads/books/a3f9.pdf',
  MODIFY COLUMN `orig_name` varchar(255) NOT NULL COMMENT '用户上传时的原始文件名，仅用于下载',
  MODIFY COLUMN `mime` varchar(64) NOT NULL COMMENT 'MIME 类型，读取时回写响应头',
  MODIFY COLUMN `size_bytes` bigint NOT NULL COMMENT '文件字节数',
  MODIFY COLUMN `sha256` varchar(64) DEFAULT NULL COMMENT '内容 SHA-256，用于去重与完整性校验',
  MODIFY COLUMN `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  MODIFY COLUMN `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间（UTC），MySQL 侧带 ON UPDATE';""",

    """ALTER TABLE `file_object` COMMENT = '文件元数据：教材 PDF、作业照片、头像；路径只存相对 DATA_ROOT 的一段';""",

    """ALTER TABLE `import_batch`
  MODIFY COLUMN `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  MODIFY COLUMN `child_id` bigint NOT NULL COMMENT '归属孩子',
  MODIFY COLUMN `raw_text` text NOT NULL COMMENT '家长从聊天记录粘贴进来的原始文本',
  MODIFY COLUMN `parsed` json DEFAULT NULL COMMENT '解析出的任务清单 JSON，导入前可人工改',
  MODIFY COLUMN `item_count` int NOT NULL COMMENT '解析出的任务条数',
  MODIFY COLUMN `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  MODIFY COLUMN `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间（UTC），MySQL 侧带 ON UPDATE';""",

    """ALTER TABLE `import_batch` COMMENT = '作业导入批次：保留原始文本与解析结果，解析错了能回看';""",

    """ALTER TABLE `mistake`
  MODIFY COLUMN `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  MODIFY COLUMN `child_id` bigint NOT NULL COMMENT '归属孩子',
  MODIFY COLUMN `subject` varchar(16) NOT NULL COMMENT '科目',
  MODIFY COLUMN `point` varchar(128) NOT NULL COMMENT '知识点，如「两位数进位加法」',
  MODIFY COLUMN `stem` text NOT NULL COMMENT '题干文本；有照片时可为空',
  MODIFY COLUMN `answer_own` text COMMENT '孩子当时的答案（错误答案）',
  MODIFY COLUMN `answer_right` text COMMENT '正确答案',
  MODIFY COLUMN `cause` varchar(32) DEFAULT NULL COMMENT '错因：计算错 / 看错题 / 概念不清 / 不会做',
  MODIFY COLUMN `stage` int NOT NULL COMMENT '复习轮次 0-4，对应间隔 1/2/4/7 天',
  MODIFY COLUMN `due_date` date DEFAULT NULL COMMENT '下次应复习的日期；已掌握则为空',
  MODIFY COLUMN `mastered` tinyint(1) NOT NULL COMMENT '是否已掌握（连对 4 次置真）',
  MODIFY COLUMN `file_id` bigint DEFAULT NULL COMMENT '错题照片 file_object.id，OCR 录入时才有',
  MODIFY COLUMN `deleted_at` datetime DEFAULT NULL COMMENT '软删除时间，非空即视为已删除',
  MODIFY COLUMN `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  MODIFY COLUMN `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间（UTC），MySQL 侧带 ON UPDATE';""",

    """ALTER TABLE `mistake` COMMENT = '错题本：按间隔重复安排复习，到期自动生成今日任务';""",

    """ALTER TABLE `reward`
  MODIFY COLUMN `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  MODIFY COLUMN `child_id` bigint NOT NULL COMMENT '归属孩子',
  MODIFY COLUMN `name` varchar(64) NOT NULL COMMENT '奖励名称，如「看动画片 20 分钟」',
  MODIFY COLUMN `cost` int NOT NULL COMMENT '兑换所需星星数',
  MODIFY COLUMN `status` varchar(16) NOT NULL COMMENT '状态：on 可兑换 / off 已下架',
  MODIFY COLUMN `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  MODIFY COLUMN `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间（UTC），MySQL 侧带 ON UPDATE';""",

    """ALTER TABLE `reward` COMMENT = '奖励项：家长设定的可兑换内容与所需星星';""",

    """ALTER TABLE `star_ledger`
  MODIFY COLUMN `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  MODIFY COLUMN `child_id` bigint NOT NULL COMMENT '归属孩子',
  MODIFY COLUMN `delta` int NOT NULL COMMENT '变动值：正数为获得，负数为消耗',
  MODIFY COLUMN `reason` varchar(32) NOT NULL COMMENT '事由，如「完成任务」「兑换奖励」「家长补发」',
  MODIFY COLUMN `ref_type` varchar(16) DEFAULT NULL COMMENT '关联业务类型：task / reward / manual',
  MODIFY COLUMN `ref_id` bigint DEFAULT NULL COMMENT '关联业务主键，与 ref_type 一起定位来源',
  MODIFY COLUMN `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  MODIFY COLUMN `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间（UTC），MySQL 侧带 ON UPDATE';""",

    """ALTER TABLE `star_ledger` COMMENT = '星星流水：只记增减不存余额，余额由 delta 求和得出';""",

    """ALTER TABLE `task`
  MODIFY COLUMN `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  MODIFY COLUMN `child_id` bigint NOT NULL COMMENT '归属孩子',
  MODIFY COLUMN `subject` varchar(16) NOT NULL COMMENT '科目：语文 / 数学 / 英语 / 体育 / 其他',
  MODIFY COLUMN `title` varchar(128) NOT NULL COMMENT '任务标题，如「口算 20 题」「语文作业」',
  MODIFY COLUMN `kind` varchar(16) NOT NULL COMMENT '任务类型：normal 普通 / redo 错题重做 / calc 口算',
  MODIFY COLUMN `minutes_est` int NOT NULL COMMENT '预估时长（分钟），用于总量控制',
  MODIFY COLUMN `stars` int NOT NULL COMMENT '完成后可得的星星数，审核通过才入账',
  MODIFY COLUMN `status` varchar(16) NOT NULL COMMENT '状态：todo 待做 / doing 进行中 / submitted 待审核 / done 已完成 / rejected 被退回',
  MODIFY COLUMN `source` varchar(16) NOT NULL COMMENT '来源：manual 手动布置 / import 粘贴导入 / mistake 错题到期生成',
  MODIFY COLUMN `source_ref` varchar(64) DEFAULT NULL COMMENT '来源引用，如 mistake:123；与 task_date 组成唯一键保证幂等',
  MODIFY COLUMN `task_date` date NOT NULL COMMENT '所属日期（本地日，不带时区）',
  MODIFY COLUMN `spent_sec` int NOT NULL COMMENT '累计用时（秒）',
  MODIFY COLUMN `note` text COMMENT '备注：家长留言或孩子写的说明',
  MODIFY COLUMN `started_at` datetime DEFAULT NULL COMMENT '首次开始计时的时间（UTC）',
  MODIFY COLUMN `submitted_at` datetime DEFAULT NULL COMMENT '提交作业的时间（UTC）',
  MODIFY COLUMN `reviewed_at` datetime DEFAULT NULL COMMENT '家长审核的时间（UTC）',
  MODIFY COLUMN `deleted_at` datetime DEFAULT NULL COMMENT '软删除时间，非空即视为已删除',
  MODIFY COLUMN `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  MODIFY COLUMN `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间（UTC），MySQL 侧带 ON UPDATE';""",

    """ALTER TABLE `task` COMMENT = '学习任务：家长布置或系统生成，状态机见 status 字段';""",

    """ALTER TABLE `book`
  MODIFY COLUMN `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  MODIFY COLUMN `child_id` bigint NOT NULL COMMENT '归属孩子；教材不做共享，必须带 child_id',
  MODIFY COLUMN `title` varchar(128) NOT NULL COMMENT '书名，如「人教版数学五年级上册」',
  MODIFY COLUMN `subject` varchar(16) NOT NULL COMMENT '科目',
  MODIFY COLUMN `grade` int NOT NULL COMMENT '年级 1-6',
  MODIFY COLUMN `term` varchar(8) NOT NULL COMMENT '学期：上册 / 下册',
  MODIFY COLUMN `edition` varchar(32) NOT NULL COMMENT '教材版本',
  MODIFY COLUMN `pages` int DEFAULT NULL COMMENT '页数，前端跳页用；解析失败时为空',
  MODIFY COLUMN `file_id` bigint NOT NULL COMMENT '指向 file_object 的 PDF 文件；有引用时禁止删除',
  MODIFY COLUMN `status` varchar(16) NOT NULL COMMENT '状态：ready 可用 / parsing 解析中 / failed 解析失败',
  MODIFY COLUMN `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  MODIFY COLUMN `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间（UTC），MySQL 侧带 ON UPDATE';""",

    """ALTER TABLE `book` COMMENT = '教材资源：上传的 PDF，按年级与科目归档，仅本孩子可见';""",

    """ALTER TABLE `mistake_log`
  MODIFY COLUMN `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  MODIFY COLUMN `mistake_id` bigint NOT NULL COMMENT '所属错题',
  MODIFY COLUMN `action` varchar(16) NOT NULL COMMENT '动作：add 录入 / redo 重做 / master 标记掌握 / reopen 重新打开',
  MODIFY COLUMN `is_correct` tinyint(1) DEFAULT NULL COMMENT '本次作答是否正确；纯录入类动作可为空',
  MODIFY COLUMN `answer` text COMMENT '本次作答内容',
  MODIFY COLUMN `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  MODIFY COLUMN `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间（UTC），MySQL 侧带 ON UPDATE';""",

    """ALTER TABLE `mistake_log` COMMENT = '错题重做流水：每一次作答都留痕，用于家长端查看重做记录';""",

    """ALTER TABLE `task_review`
  MODIFY COLUMN `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  MODIFY COLUMN `task_id` bigint NOT NULL COMMENT '被审核的任务',
  MODIFY COLUMN `reviewer_id` bigint DEFAULT NULL COMMENT '审核人 account.id，自用场景通常就是家长本人',
  MODIFY COLUMN `action` varchar(16) NOT NULL COMMENT '动作：approve 通过并发星 / reject 退回重做',
  MODIFY COLUMN `comment` varchar(255) DEFAULT NULL COMMENT '家长评语，退回时说明原因',
  MODIFY COLUMN `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  MODIFY COLUMN `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间（UTC），MySQL 侧带 ON UPDATE';""",

    """ALTER TABLE `task_review` COMMENT = '任务审核流水：通过或退回各记一条，保留完整历史';""",

    """ALTER TABLE `task_shot`
  MODIFY COLUMN `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  MODIFY COLUMN `task_id` bigint NOT NULL COMMENT '所属任务，任务删除时级联删除',
  MODIFY COLUMN `file_id` bigint NOT NULL COMMENT '指向 file_object；有引用时禁止删除文件记录',
  MODIFY COLUMN `width` int DEFAULT NULL COMMENT '原图宽度（像素），前端按比例排版',
  MODIFY COLUMN `height` int DEFAULT NULL COMMENT '原图高度（像素），前端按比例排版',
  MODIFY COLUMN `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  MODIFY COLUMN `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间（UTC），MySQL 侧带 ON UPDATE';""",

    """ALTER TABLE `task_shot` COMMENT = '作业照片：任务提交时上传的图片，按上传顺序展示';""",

)


def upgrade() -> None:
    for stmt in _UPGRADE:
        op.execute(stmt)


def downgrade() -> None:
    """清空注释。只剥离 COMMENT 子句，不重写列定义。"""
    for stmt in _UPGRADE:
        stmt = re.sub(r"COMMENT\s*=\s*'(?:[^']|'')*'", "COMMENT = ''", stmt)
        stmt = re.sub(r"COMMENT\s+'(?:[^']|'')*'", "COMMENT ''", stmt)
        op.execute(stmt)
