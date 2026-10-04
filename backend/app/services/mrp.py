"""MRP 净需求与产能/提前期预警（后端真·处理，读数据库）。

支持输入 demand_orders（既有订单或预测需求）与 production（来自优化器/heuristic 的生产方案）；
若省略，则按订单确定性生成。
"""
from collections import defaultdict

from ..models import BOMMapping, Inventory, Material, Order, Product, ScheduledReceipt


def _weeks(lead_days: int) -> int:
    return max(1, round(lead_days / 7))


def _read_demand(db, products, demand_orders, mult):
    """返回 (demand: {week:{code:qty}}, horizon)。"""
    if demand_orders is None:
        order_to_code = {p.id: p.code for p in products}
        rows = db.query(Order).all()
        horizon = max((o.week for o in rows), default=4)
        demand = defaultdict(lambda: defaultdict(int))
        for o in rows:
            code = order_to_code.get(o.product_id)
            if code:
                demand[o.week][code] += int(round(o.qty * mult))
        return demand, horizon
    horizon = max((o["week"] for o in demand_orders), default=4)
    demand = defaultdict(lambda: defaultdict(int))
    for o in demand_orders:
        demand[o["week"]][o["code"]] += int(round(o["qty"] * mult))
    return demand, horizon


def run_mrp(db, capacity_week: int = 2900, mult: float = 1.0,
            demand_orders=None, production=None):
    products = db.query(Product).all()
    materials = db.query(Material).all()
    bom_rows = db.query(BOMMapping).all()
    receipts = db.query(ScheduledReceipt).all()
    inv_rows = db.query(Inventory).all()
    inventory_by_mat = {inv.material_id: inv for inv in inv_rows}

    prod_by_code = {p.code: p for p in products}
    bom_by_product = defaultdict(dict)
    for b in bom_rows:
        bom_by_product[b.product_id][b.material_id] = b.qty
    receipt_by_mat = defaultdict(list)
    for r in receipts:
        receipt_by_mat[r.material_id].append(r)

    demand, horizon = _read_demand(db, products, demand_orders, mult)

    # ---- 生产计划 ----
    weekly_total = defaultdict(int)
    warnings = []
    production_plan = {}
    for w in range(1, horizon + 1):
        if production is None:
            production_w = {code: demand[w].get(code, 0) for code in prod_by_code}
        else:
            production_w = dict(production.get(w, {}))
        production_plan[w] = production_w
        week_sum = sum(production_w.values())
        weekly_total[w] = week_sum
        if capacity_week > 0 and week_sum > capacity_week:
            warnings.append({
                "type": "capacity", "week": w, "planned": week_sum,
                "capacity": capacity_week, "over": week_sum - capacity_week,
            })

    # ---- MRP：毛需求→净需求（提前期按子件自身，补货后结转=安全库存）----
    gross = defaultdict(lambda: defaultdict(int))
    for w in range(1, horizon + 1):
        for code, qty in production_plan[w].items():
            pid = prod_by_code[code].id
            for mid, need in bom_by_product[pid].items():
                gross[mid][w] += qty * need

    net_total = defaultdict(int)
    purchases = []
    for m in materials:
        running = inventory_by_mat[m.id].on_hand if m.id in inventory_by_mat else m.on_hand
        lw = _weeks(m.lead_days)
        for w in range(1, horizon + 1):
            g = gross[m.id].get(w, 0)
            for r in receipt_by_mat[m.id]:
                if r.week == w:
                    running += r.qty
            proj = running - g
            if proj < m.safety_stock:
                need = m.safety_stock - proj
                order_week = w - lw
                urgent = order_week < 1
                eff = max(1, order_week)
                running = m.safety_stock
                net_total[m.id] += need
                purchases.append({
                    "material_code": m.code, "material_id": m.id,
                    "supplier_id": m.supplier_id, "qty": need, "week": w,
                    "order_week": eff, "arrival_week": eff + lw, "urgent": urgent,
                    "amount": float(need) * float(m.cost),
                })
                if urgent:
                    warnings.append({
                        "type": "lead_time", "material": m.code,
                        "lead_days": m.lead_days, "week": w, "qty": need,
                        "arrival_week": eff + lw,
                    })

    mrp_out = {}
    for m in materials:
        mrp_on_hand = inventory_by_mat[m.id].on_hand if m.id in inventory_by_mat else m.on_hand
        mrp_out[m.code] = {
            "gross": {str(w): gross[m.id].get(w, 0) for w in range(1, horizon + 1)},
            "on_hand": mrp_on_hand, "safety": m.safety_stock, "net": net_total[m.id],
        }

    return {
        "horizon": horizon,
        "demand": {str(w): dict(demand[w]) for w in range(1, horizon + 1)},
        "production_plan": {str(w): dict(production_plan[w]) for w in range(1, horizon + 1)},
        "weekly_total": {str(w): weekly_total[w] for w in range(1, horizon + 1)},
        "mrp": mrp_out,
        "warnings": warnings,
        "purchases": purchases,
    }