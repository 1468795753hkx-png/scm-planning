"""初始化数据库并灌入与演示一致的主数据。运行：python -m backend.app.seed"""
from datetime import date, timedelta

from .auth import hash_password
from .database import SessionLocal, init_db
from .models import (
    BOMMapping,
    CapacityRecord,
    ForecastHistory,
    Inventory,
    Material,
    Order,
    Product,
    ScheduledReceipt,
    Supplier,
    User,
)

# 按演示一致的历史销量（趋势 + 季节 + 波动，固定）
HISTORY = {
    "P-A": [951, 983, 1032, 1066, 1105, 1172, 1185, 1212, 1245, 1316, 1367, 1423],
    "P-B": [682, 723, 757, 757, 793, 827, 831, 848, 906, 912, 941, 960],
    "P-C": [364, 359, 378, 393, 395, 417, 426, 448, 447, 466, 488, 504],
}


def seed():
    init_db()
    db = SessionLocal()
    try:
        sup = {}
        for code, lead, cap, rel in [("S1", 7, 2000, 0.95), ("S2", 14, 1500, 0.90),
                                     ("S3", 5, 1800, 0.97), ("S4", 21, 1200, 0.85)]:
            s = Supplier(name=f"供应商{code}", lead_time_days=lead, capacity=cap, reliability=rel)
            db.add(s); sup[code] = s

        prods = {}
        for code, name, cost in [("P-A", "成品A", 40), ("P-B", "成品B", 55), ("P-C", "成品C", 62)]:
            p = Product(code=code, name=name, unit_cost=cost)
            db.add(p); prods[code] = p

        mat = {}
        specs = [
            ("M001", "M001原材料", "Raw", 5, 7, "S1", 300, 3600, False),
            ("M002", "M002组件", "Comp", 12, 14, "S2", 150, 3400, False),
            ("M003", "M003组件", "Comp", 8, 5, "S3", 200, 7600, False),
            ("M004", "M004关键长交期件", "Comp", 18, 21, "S4", 100, 200, True),
        ]
        for code, name, typ, cost, lead, s, safety, oh, crit in specs:
            m = Material(code=code, name=name, type=typ, cost=cost, lead_days=lead,
                         supplier_id=sup[s].id, safety_stock=safety, on_hand=oh, critical=crit)
            db.add(m); mat[code] = m

        db.flush()  # 取得 id

        bom = {
            "P-A": {"M001": 2, "M002": 1, "M003": 4},
            "P-B": {"M001": 1, "M002": 2, "M003": 3},
            "P-C": {"M001": 1, "M003": 2, "M004": 1},
        }
        for pc, items in bom.items():
            for mc, qty in items.items():
                db.add(BOMMapping(product_id=prods[pc].id, material_id=mat[mc].id, qty=qty))

        orders = [
            ("P-A", 1, 1200), ("P-A", 2, 1350), ("P-A", 3, 1480), ("P-A", 4, 1420),
            ("P-B", 1, 850), ("P-B", 2, 900), ("P-B", 3, 880), ("P-B", 4, 950),
            ("P-C", 1, 420), ("P-C", 2, 450), ("P-C", 3, 430), ("P-C", 4, 470),
        ]
        base = date(2026, 9, 7)
        for pc, week, qty in orders:
            db.add(Order(product_id=prods[pc].id, week=week, qty=qty))
            for i, h in enumerate(HISTORY[pc]):
                db.add(ForecastHistory(product_id=prods[pc].id,
                                       period=base - timedelta(weeks=11 - i), qty=h))

        for mc, oh in [("M001", 3600), ("M002", 3400), ("M003", 7600), ("M004", 200)]:
            db.add(Inventory(material_id=mat[mc].id, on_hand=oh, in_transit=0))

        db.add(ScheduledReceipt(material_id=mat["M001"].id, week=1, qty=300))
        db.add(ScheduledReceipt(material_id=mat["M002"].id, week=2, qty=200))

        for w in range(1, 5):
            db.add(CapacityRecord(week=w, capacity_qty=2900))

        # 角色用户：admin / planner / viewer（密码哈希存储）
        for uname, pwd, role in [("admin", "admin123", "admin"),
                                 ("planner", "plan123", "planner"),
                                 ("viewer", "view123", "viewer")]:
            db.add(User(username=uname, password_hash=hash_password(pwd), role=role))

        db.commit()
        print("seed ok: suppliers=4 products=3 materials=4 bom=9 orders=12 history=36 cap=4 users=3")
    finally:
        db.close()


if __name__ == "__main__":
    seed()