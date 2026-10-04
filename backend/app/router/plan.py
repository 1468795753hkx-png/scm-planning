"""计划算法接口：/forecast、/plan/run、/plan/optimize（阶段 B：真实预测 + MILP）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_roles
from ..database import get_db
from ..models import Order, PlanRun, Product
from ..schemas import ForecastRequest, PlanRunRequest
from ..services.forecast import run_forecast
from ..services.mrp import run_mrp
from ..services.optimizer import heuristic_plan, heuristic_cost_ot, milp_plan, _demand_map

router = APIRouter(prefix="/api", tags=["plan"])
_planeer = Depends(require_roles("admin", "planner"))


def _build_orders(db, use_forecast: bool, horizon: int):
    """返回 (orders:[{code,week,qty}], forecast:dict|None)。"""
    if use_forecast:
        fc = run_forecast(db, None, horizon)
        orders = []
        for code, info in fc.items():
            for i, q in enumerate(info["weeks"], 1):
                if q > 0:
                    orders.append({"code": code, "week": i, "qty": q})
        return orders, fc

    products = db.query(Product).all()
    o2c = {p.id: p.code for p in products}
    orders = []
    for o in db.query(Order).all():
        code = o2c.get(o.product_id)
        if code:
            orders.append({"code": code, "week": o.week, "qty": o.qty})
    return orders, None


def _run(req: PlanRunRequest, db: Session, with_optimize: bool):
    orders, fc = _build_orders(db, req.use_forecast, 4)
    if not orders:
        raise HTTPException(400, "no demand data")

    products = db.query(Product).all()
    codes = [p.code for p in products]
    unit_cost = {p.code: float(p.unit_cost) for p in products}
    demand_map = _demand_map(orders, max((o["week"] for o in orders), default=4))
    horizon = max(demand_map.keys(), default=4)

    production_override = None
    optimization = None
    overtime = None
    if with_optimize and req.optimize_method == "milp":
        prod, cost, status, otime = milp_plan(demand_map, codes, req.capacity_week, horizon, unit_cost)
        if prod is None:
            prod = heuristic_plan(demand_map, codes, horizon)
            production_override = prod
            optimization = {"method": "milp", "status": status,
                            "note": "产能（含加班上限）仍不足以覆盖需求，已回退启发式"}
        else:
            production_override = prod
            overtime = otime
            hcost = heuristic_cost_ot(demand_map, codes, horizon, unit_cost, req.capacity_week)
            saving = max(0.0, hcost - cost)
            optimization = {
                "method": "milp", "status": status,
                "milp_cost": round(cost, 2), "heuristic_cost": round(hcost, 2),
                "saving": round(saving, 2),
            }
    else:
        optimization = {"method": req.optimize_method or "heuristic"}

    result = run_mrp(db, capacity_week=req.capacity_week, mult=req.mult,
                     demand_orders=orders, production=production_override)
    result["optimization"] = optimization
    if overtime is not None:
        result["overtime"] = overtime
    if fc:
        result["forecast"] = fc
    result["demand_source"] = "forecast" if fc else "orders"

    run = PlanRun(method=optimization["method"], input={"request": req.model_dump()}, output=result)
    db.add(run)
    db.commit()
    db.refresh(run)
    result["run_id"] = run.id
    return result


@router.post("/forecast")
def forecast(req: ForecastRequest, db: Session = Depends(get_db), _u: dict = _planeer):
    fc = run_forecast(db, req.product_ids, req.horizon_weeks)
    return {"forecast": fc, "count": len(fc)}


@router.post("/plan/run")
def plan_run(req: PlanRunRequest, db: Session = Depends(get_db), _u: dict = _planeer):
    return _run(req, db, with_optimize=True)


@router.post("/plan/optimize")
def plan_optimize(req: PlanRunRequest, db: Session = Depends(get_db), _u: dict = _planeer):
    result = _run(req, db, with_optimize=True)
    return {"optimization": result["optimization"], "production_plan": result["production_plan"]}