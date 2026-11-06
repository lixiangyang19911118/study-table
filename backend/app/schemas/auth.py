"""认证与孩子档案的请求/响应模型。

只约束入口形状，不做业务校验；业务规则（年级 1-6、昵称非空）写在这里
就够——它们本来就是「输入是否合法」，不需要知道数据库。
"""
from pydantic import BaseModel, ConfigDict, Field


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=32, description="登录名")
    password: str = Field(min_length=1, max_length=72, description="登录口令")


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str


class ChildOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    grade: int
    edition: str


class ChildCreate(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    grade: int = Field(default=3, ge=1, le=6)
    edition: str = Field(default="人教版", max_length=32)


class ChildPatch(BaseModel):
    """全部字段可选：PATCH 语义是「只改传了的那几个」。

    用 exclude_unset 区分「没传」和「传了空值」，见 children.update。
    """

    name: str | None = Field(default=None, min_length=1, max_length=32)
    grade: int | None = Field(default=None, ge=1, le=6)
    edition: str | None = Field(default=None, max_length=32)


class MeOut(BaseModel):
    account: AccountOut
    children: list[ChildOut]
