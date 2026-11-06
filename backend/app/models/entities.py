"""15 张表，对应技术方案 v1.1 第 05 章。

几条贯穿全表的约定：
- 所有业务表带 child_id，第一版只用得到一个孩子，但模型先留位置。
- 文件只存 file_id，路径只出现在 file_object.rel_path 一处。
- 星星不存余额，只存 star_ledger 流水，余额用 SUM 聚合。
- 周报不存快照，实时 GROUP BY。
- 时间存 UTC naive；task_date 这类「哪一天」的字段用 DATE，不带时区。

所有表与字段都带 comment，MySQL 客户端里直接看得到语义，
不必回头翻代码。新增字段时请一并补上。
"""
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer,
    JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Account(Base, TimestampMixin):
    """家长账号。自用场景下一行数据，但结构按多账号设计。"""

    __tablename__ = "account"
    __table_args__ = {"comment": "家长账号：一个账号下挂一个或多个孩子"}

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    username: Mapped[str] = mapped_column(
        String(32), unique=True, comment="登录名，唯一；自用场景就是一个固定字符串"
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(20), unique=True, comment="登录手机号，可空（本机自用可先不填）"
    )
    password_hash: Mapped[Optional[str]] = mapped_column(
        String(160), comment="登录口令的 scrypt 散列，不存明文"
    )
    nickname: Mapped[str] = mapped_column(
        String(32), default="家长", comment="家长昵称，孩子端用来称呼"
    )
    pin_hash: Mapped[Optional[str]] = mapped_column(
        String(160), comment="家长端二次确认 PIN 的散列，审核发星前校验"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="active", comment="账号状态：active 正常 / disabled 停用"
    )


class Child(Base, TimestampMixin):
    """孩子档案。年级决定内容分级，昵称用于界面称呼，不采集真名。"""

    __tablename__ = "child"
    __table_args__ = {"comment": "孩子档案：年级与偏好设置，所有业务数据按 child_id 归属"}

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("account.id", ondelete="CASCADE"), index=True,
        comment="所属家长账号，账号删除时级联删除孩子",
    )
    name: Mapped[str] = mapped_column(
        String(32), comment="孩子昵称（不采集真实姓名）"
    )
    grade: Mapped[int] = mapped_column(
        Integer, default=3, comment="年级 1-6，用于内容与教材分级"
    )
    edition: Mapped[str] = mapped_column(
        String(32), default="人教版", comment="默认教材版本，如人教版、苏教版"
    )
    avatar_file_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, comment="头像文件 id，指向 file_object"
    )
    prefs: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        comment="偏好设置 JSON：daily_cap 每日上限 / calc_range 口算范围 / "
                "daily_time 提醒时间 / 提醒开关",
    )


class FileObject(Base, TimestampMixin):
    """文件登记表。路径只在这张表出现，换存储后端只改这里。"""

    __tablename__ = "file_object"
    __table_args__ = (
        Index("ix_file_child_biz", "child_id", "biz_type"),
        {"comment": "文件元数据：教材 PDF、作业照片、头像；路径只存相对 DATA_ROOT 的一段"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    child_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("child.id", ondelete="SET NULL"),
        comment="归属孩子，孩子删除后置空但保留文件记录",
    )
    biz_type: Mapped[str] = mapped_column(
        String(16), comment="业务类型：book 教材 / shot 作业照片 / avatar 头像"
    )
    rel_path: Mapped[str] = mapped_column(
        String(255), comment="相对 DATA_ROOT 的路径，如 uploads/books/a3f9.pdf"
    )
    orig_name: Mapped[str] = mapped_column(
        String(255), default="", comment="用户上传时的原始文件名，仅用于下载"
    )
    mime: Mapped[str] = mapped_column(
        String(64), default="application/octet-stream", comment="MIME 类型，读取时回写响应头"
    )
    size_bytes: Mapped[int] = mapped_column(
        BigInteger, default=0, comment="文件字节数"
    )
    sha256: Mapped[Optional[str]] = mapped_column(
        String(64), index=True, comment="内容 SHA-256，用于去重与完整性校验"
    )


class Task(Base, TimestampMixin):
    """任务主表。状态机 todo → doing → submitted → done / rejected。"""

    __tablename__ = "task"
    __table_args__ = (
        # 错题生成的今日任务幂等：同一天同一条错题只允许一条任务
        UniqueConstraint("child_id", "task_date", "source_ref", name="uk_task_source"),
        Index("ix_task_child_date_status", "child_id", "task_date", "status"),
        {"comment": "学习任务：家长布置或系统生成，状态机见 status 字段"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("child.id", ondelete="CASCADE"), index=True,
        comment="归属孩子",
    )
    subject: Mapped[str] = mapped_column(
        String(16), default="语文", comment="科目：语文 / 数学 / 英语 / 体育 / 其他"
    )
    title: Mapped[str] = mapped_column(
        String(128), comment="任务标题，如「口算 20 题」「语文作业」"
    )
    kind: Mapped[str] = mapped_column(
        String(16), default="normal",
        comment="任务类型：normal 普通 / redo 错题重做 / calc 口算",
    )
    minutes_est: Mapped[int] = mapped_column(
        Integer, default=20, comment="预估时长（分钟），用于总量控制"
    )
    stars: Mapped[int] = mapped_column(
        Integer, default=1, comment="完成后可得的星星数，审核通过才入账"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="todo",
        comment="状态：todo 待做 / doing 进行中 / submitted 待审核 / "
                "done 已完成 / rejected 被退回",
    )
    source: Mapped[str] = mapped_column(
        String(16), default="manual",
        comment="来源：manual 手动布置 / import 粘贴导入 / mistake 错题到期生成",
    )
    source_ref: Mapped[Optional[str]] = mapped_column(
        String(64), comment="来源引用，如 mistake:123；与 task_date 组成唯一键保证幂等"
    )
    task_date: Mapped[date] = mapped_column(
        Date, index=True, comment="所属日期（本地日，不带时区）"
    )
    spent_sec: Mapped[int] = mapped_column(
        Integer, default=0, comment="累计用时（秒）"
    )
    note: Mapped[Optional[str]] = mapped_column(
        Text, comment="备注：家长留言或孩子写的说明"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, comment="首次开始计时的时间（UTC）"
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, comment="提交作业的时间（UTC）"
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, comment="家长审核的时间（UTC）"
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, comment="软删除时间，非空即视为已删除"
    )


class TaskShot(Base, TimestampMixin):
    """作业照片，一张任务可有多张。"""

    __tablename__ = "task_shot"
    __table_args__ = (
        Index("ix_shot_task", "task_id"),
        {"comment": "作业照片：任务提交时上传的图片，按上传顺序展示"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    task_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("task.id", ondelete="CASCADE"),
        comment="所属任务，任务删除时级联删除",
    )
    file_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("file_object.id", ondelete="RESTRICT"),
        comment="指向 file_object；有引用时禁止删除文件记录",
    )
    width: Mapped[Optional[int]] = mapped_column(
        Integer, comment="原图宽度（像素），前端按比例排版"
    )
    height: Mapped[Optional[int]] = mapped_column(
        Integer, comment="原图高度（像素），前端按比例排版"
    )


class TaskReview(Base, TimestampMixin):
    """审核流水。退回重做会新增一条，不覆盖历史。"""

    __tablename__ = "task_review"
    __table_args__ = {"comment": "任务审核流水：通过或退回各记一条，保留完整历史"}

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    task_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("task.id", ondelete="CASCADE"), index=True,
        comment="被审核的任务",
    )
    reviewer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, comment="审核人 account.id，自用场景通常就是家长本人"
    )
    action: Mapped[str] = mapped_column(
        String(16), comment="动作：approve 通过并发星 / reject 退回重做"
    )
    comment: Mapped[Optional[str]] = mapped_column(
        String(255), comment="家长评语，退回时说明原因"
    )


class Mistake(Base, TimestampMixin):
    """错题本。复习节奏 1/2/4/7 天，连对 4 次视为掌握。"""

    __tablename__ = "mistake"
    __table_args__ = (
        Index("ix_mistake_due", "child_id", "mastered", "due_date"),
        {"comment": "错题本：按间隔重复安排复习，到期自动生成今日任务"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("child.id", ondelete="CASCADE"), index=True,
        comment="归属孩子",
    )
    subject: Mapped[str] = mapped_column(
        String(16), default="数学", comment="科目"
    )
    point: Mapped[str] = mapped_column(
        String(128), default="", comment="知识点，如「两位数进位加法」"
    )
    stem: Mapped[str] = mapped_column(
        Text, default="", comment="题干文本；有照片时可为空"
    )
    answer_own: Mapped[Optional[str]] = mapped_column(
        Text, comment="孩子当时的答案（错误答案）"
    )
    answer_right: Mapped[Optional[str]] = mapped_column(
        Text, comment="正确答案"
    )
    cause: Mapped[Optional[str]] = mapped_column(
        String(32), comment="错因：计算错 / 看错题 / 概念不清 / 不会做"
    )
    stage: Mapped[int] = mapped_column(
        Integer, default=0, comment="复习轮次 0-4，对应间隔 1/2/4/7 天"
    )
    due_date: Mapped[Optional[date]] = mapped_column(
        Date, comment="下次应复习的日期；已掌握则为空"
    )
    mastered: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否已掌握（连对 4 次置真）"
    )
    file_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, comment="错题照片 file_object.id，OCR 录入时才有"
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, comment="软删除时间，非空即视为已删除"
    )


class MistakeLog(Base, TimestampMixin):
    """错题流水：新增、重做、掌握、重新打开都记一条。"""

    __tablename__ = "mistake_log"
    __table_args__ = (
        Index("ix_mlog_time", "mistake_id", "created_at"),
        {"comment": "错题重做流水：每一次作答都留痕，用于家长端查看重做记录"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    mistake_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mistake.id", ondelete="CASCADE"),
        comment="所属错题",
    )
    action: Mapped[str] = mapped_column(
        String(16), comment="动作：add 录入 / redo 重做 / master 标记掌握 / reopen 重新打开"
    )
    is_correct: Mapped[Optional[bool]] = mapped_column(
        Boolean, comment="本次作答是否正确；纯录入类动作可为空"
    )
    answer: Mapped[Optional[str]] = mapped_column(
        Text, comment="本次作答内容"
    )


class CalcRecord(Base, TimestampMixin):
    """一次口算练习的成绩单。"""

    __tablename__ = "calc_record"
    __table_args__ = {"comment": "口算记录：每完成一轮记一条，用于家长端看正确率与用时"}

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("child.id", ondelete="CASCADE"), index=True,
        comment="归属孩子",
    )
    task_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, comment="关联的口算任务 id；独立练习时为空"
    )
    # 注意：range 是 MySQL 保留字，列名必须是 range_max
    range_max: Mapped[int] = mapped_column(
        Integer, default=100, comment="数值范围上限：10 / 20 / 100（列名避开保留字 range）"
    )
    total: Mapped[int] = mapped_column(
        Integer, default=0, comment="本轮总题数"
    )
    right_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="答对题数"
    )
    seconds: Mapped[int] = mapped_column(
        Integer, default=0, comment="本轮用时（秒）"
    )
    types: Mapped[Optional[list[str]]] = mapped_column(
        JSON, comment="题型数组：add/sub/fill_addend/fill_minuend/fill_sum/"
                      "fill_diff/chain_add/chain_sub"
    )


class Book(Base, TimestampMixin):
    """教材。只对上传者本人可见，不做共享库。"""

    __tablename__ = "book"
    __table_args__ = (
        Index("ix_book_filter", "child_id", "grade", "subject"),
        {"comment": "教材资源：上传的 PDF，按年级与科目归档，仅本孩子可见"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("child.id", ondelete="CASCADE"),
        comment="归属孩子；教材不做共享，必须带 child_id",
    )
    title: Mapped[str] = mapped_column(
        String(128), comment="书名，如「人教版数学五年级上册」"
    )
    subject: Mapped[str] = mapped_column(
        String(16), comment="科目"
    )
    grade: Mapped[int] = mapped_column(
        Integer, comment="年级 1-6"
    )
    term: Mapped[str] = mapped_column(
        String(8), default="上册", comment="学期：上册 / 下册"
    )
    edition: Mapped[str] = mapped_column(
        String(32), default="人教版", comment="教材版本"
    )
    pages: Mapped[Optional[int]] = mapped_column(
        Integer, comment="页数，前端跳页用；解析失败时为空"
    )
    file_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("file_object.id", ondelete="RESTRICT"),
        comment="指向 file_object 的 PDF 文件；有引用时禁止删除"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="ready", comment="状态：ready 可用 / parsing 解析中 / failed 解析失败"
    )


class Checkin(Base, TimestampMixin):
    """每日打卡。一个孩子一天最多一条。"""

    __tablename__ = "checkin"
    __table_args__ = (
        UniqueConstraint("child_id", "check_date", name="uk_checkin_day"),
        {"comment": "每日打卡：一天一条，连续天数由日期序列实时计算"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("child.id", ondelete="CASCADE"),
        comment="归属孩子",
    )
    check_date: Mapped[date] = mapped_column(
        Date, comment="打卡日期（本地日）；与 child_id 组成唯一键防重复"
    )


class StarLedger(Base, TimestampMixin):
    """星星只记流水，不记余额。孩子问「我的星星怎么少了」要能逐条对账。"""

    __tablename__ = "star_ledger"
    __table_args__ = (
        Index("ix_star_time", "child_id", "created_at"),
        {"comment": "星星流水：只记增减不存余额，余额由 delta 求和得出"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("child.id", ondelete="CASCADE"),
        comment="归属孩子",
    )
    delta: Mapped[int] = mapped_column(
        Integer, comment="变动值：正数为获得，负数为消耗"
    )
    reason: Mapped[str] = mapped_column(
        String(32), comment="事由，如「完成任务」「兑换奖励」「家长补发」"
    )
    ref_type: Mapped[Optional[str]] = mapped_column(
        String(16), comment="关联业务类型：task / reward / manual"
    )
    ref_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, comment="关联业务主键，与 ref_type 一起定位来源"
    )


class Reward(Base, TimestampMixin):
    """奖励清单，孩子用星星兑换。"""

    __tablename__ = "reward"
    __table_args__ = {"comment": "奖励项：家长设定的可兑换内容与所需星星"}

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("child.id", ondelete="CASCADE"), index=True,
        comment="归属孩子",
    )
    name: Mapped[str] = mapped_column(
        String(64), comment="奖励名称，如「看动画片 20 分钟」"
    )
    cost: Mapped[int] = mapped_column(
        Integer, default=5, comment="兑换所需星星数"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="on", comment="状态：on 可兑换 / off 已下架"
    )


class ChatMessage(Base, TimestampMixin):
    """与助手的对话记录。提示词约束为给思路不给答案。"""

    __tablename__ = "chat_message"
    __table_args__ = (
        Index("ix_chat_time", "child_id", "created_at"),
        {"comment": "助手对话记录：按时间正序回放，用于构建上下文与用量统计"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("child.id", ondelete="CASCADE"),
        comment="归属孩子",
    )
    role: Mapped[str] = mapped_column(
        String(16), comment="消息角色：user 孩子 / assistant 助手"
    )
    content: Mapped[str] = mapped_column(
        Text, comment="消息正文"
    )
    tokens: Mapped[int] = mapped_column(
        Integer, default=0, comment="本条消耗的 token 数，用于成本控制"
    )


class ImportBatch(Base, TimestampMixin):
    """粘贴导入老师作业的原始文本与解析结果，便于回溯。"""

    __tablename__ = "import_batch"
    __table_args__ = {"comment": "作业导入批次：保留原始文本与解析结果，解析错了能回看"}

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("child.id", ondelete="CASCADE"), index=True,
        comment="归属孩子",
    )
    raw_text: Mapped[str] = mapped_column(
        Text, comment="家长从聊天记录粘贴进来的原始文本"
    )
    parsed: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(
        JSON, comment="解析出的任务清单 JSON，导入前可人工改"
    )
    item_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="解析出的任务条数"
    )
