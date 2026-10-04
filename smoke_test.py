import os
import tempfile

tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite:///" + tmp.replace("\\", "/") + "/t.db"

from fastapi.testclient import TestClient  # noqa: E402

from backend.app import seed  # noqa: E402
seed.seed()

from backend.app.main import app  # noqa: E402

fail = 0


def check(name, cond, extra=""):
    global fail
    print(("OK " if cond else "FAIL ") + name + ("  " + str(extra) if extra else ""))
    if not cond:
        fail += 1


def login(client, u, p):
    r = client.post("/api/auth/login", json={"username": u, "password": p})
    return r.json().get("token"), r.json().get("role")


with TestClient(app) as c:
    # 未鉴权应 401
    check("unauth 401", c.get("/api/products").status_code == 401)
    check("health no auth", c.get("/health").status_code == 200)

    tok, role = login(c, "admin", "admin123")
    H = {"Authorization": "Bearer " + tok}
    check("admin login role", role == "admin", role)

    mats = c.get("/api/materials", headers=H).json()
    check("materials count", len(mats) == 4, [m["code"] for m in mats])

    pr = c.post("/api/plan/run", headers=H, json={"optimize_method": "milp"}).json()
    check("plan/run milp", pr.get("optimization", {}).get("method") == "milp")
    check("plan mrp M004 net>0", pr["mrp"]["M004"]["net"] > 0)

    g = c.post("/api/po/generate", headers=H, json={"run_id": pr["run_id"], "auto_cap": 30000}).json()
    check("po generate admin", g["created"] > 0, (g["auto_count"], g["manual_count"]))
    pending = [o for o in c.get("/api/po", headers=H, params={"status": "pending"}).json()]
    if pending:
        ap = c.post(f"/api/po/{pending[0]['id']}/approve?action=approve", headers=H)
        check("po approve admin", ap.status_code == 200, ap.json().get("status"))

    fe = c.post("/api/forecast", headers=H, json={"horizon_weeks": 4}).json()
    check("forecast", set(fe["forecast"]) == {"P-A", "P-B", "P-C"})

    # RBAC：viewer 只读，写/管理 403
    vtok, vrole = login(c, "viewer", "view123")
    V = {"Authorization": "Bearer " + vtok}
    check("viewer role", vrole == "viewer", vrole)
    check("viewer read products 200", c.get("/api/products", headers=V).status_code == 200)
    # 所有写操作：viewer 应 403（中间件 RBAC）
    check("viewer POST product 403",
          c.post("/api/products", headers=V, json={"code": "P-X", "name": "x"}).status_code == 403)
    check("viewer POST order 403",
          c.post("/api/orders", headers=V, json={"product_id": "x", "week": 1, "qty": 1}).status_code == 403)
    check("viewer UPSERT inventory 403",
          c.post("/api/inventory", headers=V, json={"material_id": "x", "on_hand": 0}).status_code == 403)
    check("viewer plan/run 403",
          c.post("/api/plan/run", headers=V, json={}).status_code == 403)
    check("viewer forecast 403",
          c.post("/api/forecast", headers=V, json={}).status_code == 403)
    check("viewer po/generate 403",
          c.post("/api/po/generate", headers=V, json={"run_id": pr["run_id"]}).status_code == 403)
    if pending:
        check("viewer approve 403",
              c.post(f"/api/po/{pending[0]['id']}/approve?action=approve", headers=V).status_code == 403)
    # planner 角色可写
    ptok, prole = login(c, "planner", "plan123")
    P = {"Authorization": "Bearer " + ptok}
    check("planner role", prole == "planner")
    prun = c.post("/api/plan/run", headers=P, json={"optimize_method": "milp"}).json()
    check("planner plan/run ok", bool(prun.get("run_id")))

    # 精细权限：删除（产品/物料）仅 admin
    ptemp = c.post("/api/products", headers=H, json={"code": "P-TMP", "name": "临时"}).json()
    check("planner delete product 403",
          c.delete("/api/products/" + ptemp["id"], headers=P).status_code == 403)
    check("admin delete product ok",
          c.delete("/api/products/" + ptemp["id"], headers=H).status_code in (200, 204))

    if fail == 0:
        print("ALL_SMOKE_OK")
    else:
        print("SMOKE_FAILS=", fail)
        raise SystemExit(1)