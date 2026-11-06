"""口令散列与 JWT。

密码与家长 PIN 都用 stdlib 的 scrypt，不引第三方包：
passlib 与新版 bcrypt 长期不兼容，为一个自用项目踩这个坑不值得。
"""
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import settings

_ALGO = "HS256"
_N, _R, _P = 2 ** 14, 8, 1


def hash_secret(raw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(raw.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${dk.hex()}"


def verify_secret(raw: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        scheme, n, r, p, salt_hex, dk_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        dk = hashlib.scrypt(
            raw.encode(), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=len(dk_hex) // 2,
        )
        return hmac.compare_digest(dk.hex(), dk_hex)
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str, extra: dict[str, Any] | None = None, minutes: int | None = None
) -> str:
    """签发 JWT。

    minutes 显式传入时覆盖 ACCESS_TOKEN_MIN。会话 Cookie 走 7 天，
    这样家长不必每天重新登录；真正的 access/refresh 双令牌拆分留到
    对外提供服务时再做，单机自用没必要。
    """
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=minutes or settings.ACCESS_TOKEN_MIN),
        "typ": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=_ALGO)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[_ALGO])
