"""FastAPI 应用入口。全部 /api 路由需 JWT 鉴权；写操作（POST/PUT/PATCH/DELETE/QUERY）仅 admin/planner。"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .auth import create_access_token, decode_token, require_auth, verify_password
from .config import get_settings
from .database import get_db, init_db
from .models import User
from .router import demand, inventory, items, plan, po

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE", "QUERY"}
_MANAGERS = {"admin", "planner"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="SCM Planner API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_settings().allowed_origins),  # 白名单，生产收紧
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rbac_write_gate(request: Request, call_next):
    """写操作统一要求角色 admin/planner；读操作由各路由依赖负责鉴权。"""
    p = request.url.path
    if p.startswith("/api") and not p.startswith("/api/auth") and request.method in _WRITE_METHODS:
        auth = request.headers.get("Authorization", "")
        token = auth[7:] if auth.lower().startswith("bearer ") else ""
        try:
            payload = decode_token(token)
        except HTTPException:
            return JSONResponse({"detail": "not authenticated"}, status_code=401)
        if payload.get("role") not in _MANAGERS:
            return JSONResponse({"detail": "permission denied"}, status_code=403)
    return await call_next(request)


# 所有业务路由要求有效 token
for r in (items.router, demand.router, inventory.router, plan.router, po.router):
    app.include_router(r, dependencies=[Depends(require_auth)])


class LoginRequest(BaseModel):
    username: str
    password: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "scm-planner-api"}


@app.post("/api/auth/login")
def login(req: LoginRequest, db=Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "invalid credentials")
    return {
        "token": create_access_token(user.username, user.role),
        "role": user.role,
        "token_type": "bearer",
    }