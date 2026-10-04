"""采购订单：生成（按风险分级）、查询、审批、风险洞察。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import require_roles
from ..database import get_db
from ..models import Material, PlanRun, PurchaseOrder
from ..schemas import POGenerateRequest, PurchaseOrderOut

router = APIRouter(prefix="/api", tags=["purchase"])


def _grade(mat: Material, amt: float, urgent: bool, auto_cap: float) -> tuple[str, list[str]]:
    reasons = []
    if urgent:
        reasons.append("提前期越界")
    if mat.critical:
        reasons.append("关键长交期件")
    if amt >= auto_cap:
        reasons.append("金额超阈值")
    if reasons:
        return "pending", reasons  # 需人工审批
    return "auto", ["标准补货"]


@router.post("/po/generate")
def generate_po(req: POGenerateRequest, db: Session = Depends(get_db),
                _u: dict = Depends(require_roles("admin", "planner"))):
    run = db.get(PlanRun, req.run_id)
    if not run or not run.output:
        raise HTTPException(404, "plan run not found")

    n = db.query(PurchaseOrder).count()
    created = []
    for p in run.output.get("purchases", []):
        mat = db.get(Material, p["material_id"])
        if not mat:
            continue
        amt = p["amount"]
        status, reasons = _grade(mat, amt, p.get("urgent", False), req.auto_cap)
        n += 1
        po = PurchaseOrder(
            po_no=f"PO-{n:04d}",
            run_id=req.run_id,
            material_id=p["material_id"],
            supplier_id=p.get("supplier_id"),
            qty=p["qty"],
            order_week=p["order_week"],
            arrival_week=p["arrival_week"],
            amount=amt,
            status=status,
            reason="、".join(reasons),
        )
        db.add(po)
        created.append(po)
    db.commit()
    for po in created:
        db.refresh(po)

    auto = sum(1 for x in created if x.status == "auto")
    return {
        "created": len(created),
        "auto_count": auto,
        "manual_count": len(created) - auto,
        "orders": [PurchaseOrderOut.model_validate(po).model_dump() for po in created],
    }


@router.get("/po", response_model=list[PurchaseOrderOut])
def list_po(status: str | None = Query(None), db: Session = Depends(get_db)):
    q = db.query(PurchaseOrder)
    if status:
        q = q.filter(PurchaseOrder.status == status)
    return q.all()


@router.post("/po/{item_id}/approve", response_model=PurchaseOrderOut)
def approve_po(item_id: str, action: str = Query("approve", pattern="^(approve|reject)$"),
               db: Session = Depends(get_db),
               _u: dict = Depends(require_roles("admin", "planner"))):
    obj = db.get(PurchaseOrder, item_id)
    if not obj:
        raise HTTPException(404, "purchase order not found")
    obj.status = "approved" if action == "approve" else "rejected"
    db.commit(); db.refresh(obj)
    return obj


@router.get("/insights/risk")
def risk_insights(db: Session = Depends(get_db)):
    pending = db.query(PurchaseOrder).filter(PurchaseOrder.status == "pending").all()
    return {
        "pending_approvals": [
            {"po_no": p.po_no, "material_id": p.material_id, "qty": p.qty,
             "arrival_week": p.arrival_week, "amount": float(p.amount), "reason": p.reason}
            for p in pending
        ],
        "hint": "阶段 B 将并入 MRP 产能/提前期预警汇总",
    }