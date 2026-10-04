# SCM Planner Backend（阶段 A：CRUD + 基础 MRP）

FastAPI + SQLAlchemy + 可移植数据库（本地 SQLite，生产 PostgreSQL）后端骨架，对应《SPEC.md》阶段 A。

## 目录
```
backend/
  app/
    main.py        # 入口，挂载路由
    config.py      # 配置（DATABASE_URL / SECRET_KEY）
    database.py    # 引擎/会话/建表
    models.py      # ORM 模型（10 张表）
    schemas.py     # Pydantic 校验
    auth.py        # 开发用 JWT
    seed.py        # 建表 + 灌入主数据/BOM/订单/历史
    router/        # items / demand / inventory / plan / po
    services/      # mrp.py（后端真算 MRP）
```

## 一键启动（推荐）

项目根目录下双击 **`start-all.bat`**，或在 PowerShell 执行 `.\start-all.ps1`：

- 自动定位 Python、缺失依赖时自动 `pip install -r requirements.txt`；
- 无 `scm.db` 时自动建表并灌入演示数据（bcrypt）；
- 同时启动后端（`127.0.0.1:8000`）与前端静态页（`127.0.0.1:8080`），并自动打开浏览器；
- 在等待界面输入 `q` 回车或 Ctrl+C 可停止后端与前端；`.\start-all.ps1 -NoWait` 后台常驻。

## 快速开始（手动，本地 SQLite）

```bash
# 需 Python 3.11
pip install -r requirements.txt

# 建库并灌入演示数据
python -m backend.app.seed

# 启动
uvicorn backend.app.main:app --reload
```

- 交互式文档：http://127.0.0.1:8000/docs
- 健康检查：`GET /health`
- 登录（开发用）：`POST /api/auth/login`  body `{"username":"admin","password":"admin123"}`，返回 token，后续请求带 `Authorization: Bearer <token>`。

## 主要接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST/PUT/DELETE | `/api/products` `/api/materials` `/api/bom` `/api/suppliers` | 主数据 CRUD |
| GET/POST | `/api/orders` `/api/forecast-history` | 需求与历史 |
| GET/POST | `/api/inventory` `/api/scheduled-receipts` `/api/capacity` | 库存/在途/产能 |
| POST | `/api/plan/run` | 一键 MRP（读库真算，返回生产计划/净需求/采购建议/预警） |
| POST | `/api/forecast` `/api/plan/optimize` | 阶段 B（预测 / MILP），当前返回 501 |
| POST | `/api/po/generate` | 采购分级生成（需 admin/planner） |
| GET/POST | `/api/po` `/api/po/{id}/approve` `/api/insights/risk` | 订单查询/审批（需 admin/planner）/风险洞察 |

## 鉴权与 RBAC

- 全部 `/api/*` 需 `Authorization: Bearer <token>`（`/health`、`/api/auth/login` 除外）。
- 三个种子用户：`admin/admin123`(admin)、`planner/plan123`(planner)、`viewer/view123`(viewer)。
- RBAC（中间件统一门控）：**读操作**任何已登录用户可访问；**写操作（POST/PUT/PATCH/DELETE/QUERY，含产品/物料/订单/库存/计划/预测/采购生成与审批）仅 admin、planner**；viewer 只读（越权返回 403）。
- 更细粒度：**删除产品/物料**进一步收紧为仅 `admin`（planner 会返回 403）。
- 密码使用 **bcrypt** 哈希（演示级够用，生产建议配合任意更长密钥）。

## 生产部署（PostgreSQL + Alembic）

```bash
cp .env.example .env   # 改 DATABASE_URL/SECRET_KEY/ALLOWED_ORIGINS
python -m alembic upgrade head   # 迁移到数据库（应用未启动时执行）
docker compose up --build
```
- 迁移配置在 `alembic/`（`env.py` 从 `backend.app.config` 读 `DATABASE_URL`）；模型变更后：`python -m alembic revision --autogenerate -m "xxx"`。
- 已实测：对空库执行 `alembic upgrade head` 后 11 张业务表 + `alembic_version` 齐全（SQLite 验证通过，Postgres 同流程）。
- CORS 白名单由 `ALLOWED_ORIGINS` 控制（默认仅本地 8080；生产填真实前端域名）。

## 前端看板（阶段 C，API 驱动）

`frontend/index.html` 是与后端联通的前端：产品/物料/库存/订单读写走 `/api/*`，"运行计划/预测/生成采购订单"调用对应算法接口。

```bash
# 后端保持运行，另起静态服务器提供前端
python -m http.server 8080 --bind 127.0.0.1
# 打开 http://127.0.0.1:8080/frontend/index.html ，用 admin/admin123 登录
```
页面右上角可改后端地址（默认 `http://127.0.0.1:8000`）。CORS 白名单由 `ALLOWED_ORIGINS` 控制。登录后才可读写；viewer 登录后写操作（含计划/采购）会返回 403。

## 诚实边界
- 阶段 A/B/C 已验证：确定性 MRP（后端真算）+ statsmodels 预测 + PuLP MILP 优化 + 采购分级 + JWT/RBAC + Alembic 迁移，全链路冒烟通过。
- 生产计划采用"按需求齐套"简化（未建模成品安全库存），阶段后续再补齐。
- 密码哈希为 bcrypt；CORS 默认白名单仅本地 8080，生产需在 `ALLOWED_ORIGINS` 填真实前端域名并收紧。