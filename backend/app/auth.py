"""JWT 鉴权与 RBAC。

- require_auth: 依赖，校验 Authorization Bearer，返回 payload（含 sub/role）
- require_roles(*roles): 依赖工厂，校验当前用户角色，未授权返回 403
- 密码用 bcrypt 哈希
"""
import bcrypt
from datetime import datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings

_bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, h: str) -> bool:
    return bcrypt.checkpw(pw.encode("utf-8"), h.encode("utf-8"))


def create_access_token(username: str, role: str) -> str:
    s = get_settings()
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=s.access_token_expire_minutes),
    }
    return jwt.encode(payload, s.secret_key, algorithm="HS256")


def decode_token(token: str) -> dict:
    s = get_settings()
    try:
        return jwt.decode(token, s.secret_key, algorithms=["HS256"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from exc


def require_auth(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    return decode_token(creds.credentials)


def require_roles(*roles: str):
    def dep(payload: dict = Depends(require_auth)) -> dict:
        if payload.get("role") not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "permission denied")
        return payload
    return dep