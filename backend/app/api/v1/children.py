"""孩子档案。所有业务数据都挂在 child_id 上，所以这是 M1 的另一半。

接口按「一个账号多个孩子」设计，UI 第一版只展示一个。
多花的成本只是多一个 child_id 参数，不多写表也不多写查询。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_account, list_children, owned_child
from app.core.db import get_db
from app.models import Account, Child
from app.schemas.auth import ChildCreate, ChildOut, ChildPatch

router = APIRouter(tags=["孩子档案"])


@router.get("/children", response_model=list[ChildOut], summary="账号下的孩子列表")
def index(account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    return [ChildOut.model_validate(c) for c in list_children(account, db)]


@router.post("/children", response_model=ChildOut, summary="新建孩子档案")
def create(
    body: ChildCreate,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    child = Child(
        account_id=account.id,
        name=body.name,
        grade=body.grade,
        edition=body.edition,
    )
    db.add(child)
    db.commit()
    db.refresh(child)
    return ChildOut.model_validate(child)


@router.get("/children/{child_id}", response_model=ChildOut, summary="孩子档案详情")
def show(
    child_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    return ChildOut.model_validate(owned_child(child_id, account, db))


@router.patch("/children/{child_id}", response_model=ChildOut, summary="修改昵称/年级/版本")
def update(
    child_id: int,
    body: ChildPatch,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    child = owned_child(child_id, account, db)
    # exclude_unset：只写传了的字段。传 name="" 会被 schema 的 min_length 拦掉，
    # 传 null 则表示「不动这个字段」，不是「清空」。
    for field, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(child, field, value)
    db.commit()
    db.refresh(child)
    return ChildOut.model_validate(child)
