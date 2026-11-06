"""登录、登出、当前账号。

Cookie 而不是 Authorization 头，是这一版最关键的取舍：
`<img src="/api/v1/files/12">` 和 `<iframe>` 无法携带自定义请求头，
一旦把 JWT 放响应体让前端塞进 header，教材 PDF 与作业照片会全部 401。
详见技术方案 v1.1「缺口 1」。
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_account, list_children
from app.core.config import settings
from app.core.db import get_db
from app.core.security import create_access_token, verify_secret
from app.models import Account
from app.schemas.auth import AccountOut, ChildOut, LoginIn, MeOut

router = APIRouter(tags=["认证"])


def _me(account: Account, db: Session) -> MeOut:
    return MeOut(
        account=AccountOut.model_validate(account),
        children=[ChildOut.model_validate(c) for c in list_children(account, db)],
    )


@router.post("/auth/login", response_model=MeOut, summary="登录，成功后写 HttpOnly Cookie")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    account = db.scalar(select(Account).where(Account.username == body.username))
    # 账号不存在与密码错误返回同一句话，避免被用来探测用户名是否存在
    if account is None or not verify_secret(body.password, account.password_hash):
        raise HTTPException(401, "登录名或密码不正确")
    if account.status != "active":
        raise HTTPException(403, "账号已停用")

    token = create_access_token(
        str(account.id), minutes=settings.SESSION_DAYS * 24 * 60
    )
    response.set_cookie(
        key=settings.SESSION_COOKIE,
        value=token,
        max_age=settings.SESSION_DAYS * 86400,
        httponly=True,          # JS 读不到，XSS 拿不走
        samesite="lax",         # 跨站请求不带 Cookie，防 CSRF
        secure=settings.COOKIE_SECURE,
        path="/",
    )
    return _me(account, db)


@router.post("/auth/logout", summary="登出，清掉 Cookie")
def logout(response: Response):
    response.delete_cookie(settings.SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/auth/me", response_model=MeOut, summary="当前账号与孩子列表")
def me(account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    return _me(account, db)
