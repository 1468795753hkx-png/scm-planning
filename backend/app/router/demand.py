"""需求数据 CRUD：orders / forecast-history。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ForecastHistory, Order
from ..schemas import (
    HistoryCreate,
    HistoryOut,
    OrderCreate,
    OrderOut,
)

router = APIRouter(prefix="/api", tags=["demand"])


@router.get("/orders", response_model=list[OrderOut])
def list_orders(product_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Order)
    if product_id:
        q = q.filter(Order.product_id == product_id)
    return q.all()


@router.post("/orders", response_model=OrderOut, status_code=201)
def create_order(data: OrderCreate, db: Session = Depends(get_db)):
    obj = Order(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.delete("/orders/{item_id}", status_code=204)
def delete_order(item_id: str, db: Session = Depends(get_db)):
    obj = db.get(Order, item_id)
    if not obj:
        raise HTTPException(404, "order not found")
    db.delete(obj); db.commit()


@router.get("/forecast-history", response_model=list[HistoryOut])
def list_history(product_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(ForecastHistory)
    if product_id:
        q = q.filter(ForecastHistory.product_id == product_id)
    return q.all()


@router.post("/forecast-history", response_model=list[HistoryOut], status_code=201)
def create_history(data: list[HistoryCreate] | HistoryCreate, db: Session = Depends(get_db)):
    items = data if isinstance(data, list) else [data]
    objs = [ForecastHistory(**x.model_dump()) for x in items]
    db.add_all(objs); db.commit()
    for o in objs:
        db.refresh(o)
    return objs