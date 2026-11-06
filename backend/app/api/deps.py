"""请求上下文依赖：Cookie → 当前账号 → 当前孩子。

三条规则，后续所有接口都照这个来：

1. **身份只从这里来**。接口参数里绝不出现 account_id / child_id 让前端填，
   否则改个数字就能读到别人家的照片。M0 阶段 files.py 就是收前端传的
   child_id，M1 已经改掉。
2. **越权返回 403，不存在返回 404**。两者分开是为了排错时不至于把
   「没这个孩子」和「不是你的孩子」混为一谈。
3. **依赖里不写业务**。这里只做「你是谁」「这个孩子是不是你的」，
   业务判断留在路由或将来的 services。
"""
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import decode_token
from app.models import Account, Child


def get_current_account(request: Request, db: Session = Depends(get_db)) -> Account:
    """从 HttpOnly Cookie 解出当前账号。未登录一律 401。"""
    token = request.cookies.get(settings.SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "未登录")
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "登录已过期，请重新登录")
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(401, "登录凭证无效")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(401, "登录凭证无效")

    account = db.get(Account, int(sub))
    if account is None or account.status != "active":
        raise HTTPException(401, "账号不存在或已停用")
    return account


def list_children(account: Account, db: Session) -> list[Child]:
    """账号下的孩子，按创建顺序。第一版 UI 只用一个，接口按多个设计。"""
    return list(
        db.scalars(
            select(Child).where(Child.account_id == account.id).order_by(Child.id)
        )
    )


def owned_child(child_id: int, account: Account, db: Session) -> Child:
    """取孩子并校验归属。孩子不存在 404，不属于本账号 403。"""
    child = db.get(Child, child_id)
    if child is None:
        raise HTTPException(404, "孩子档案不存在")
    if child.account_id != account.id:
        raise HTTPException(403, "无权访问该孩子档案")
    return child


def default_child(account: Account, db: Session) -> Child:
    """没有显式指定孩子时的默认值：第一个。

    单孩子场景下前端不用传任何 id；将来做二孩，前端传 child_id 走 owned_child。
    """
    children = list_children(account, db)
    if not children:
        raise HTTPException(404, "账号下还没有孩子档案，请先在家长端创建")
    return children[0]
