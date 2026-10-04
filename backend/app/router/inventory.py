"""库存 / 在途 / 产能 CRUD。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CapacityRecord, Inventory, ScheduledReceipt
from ..schemas import (
    CapacityBase,
    CapacityOut,
    InventoryCreate,
    InventoryOut,
    ReceiptCreate,
    ReceiptOut,
)

router = APIRouter(prefix="/api", tags=["inventory"])


@router.get("/inventory", response_model=list[InventoryOut])
def list_inventory(db: Session = Depends(get_db)):
    return db.query(Inventory).all()


@router.get("/inventory/{material_id}", response_model=InventoryOut)
def get_inventory(material_id: str, db: Session = Depends(get_db)):
    obj = db.query(Inventory).filter(Inventory.material_id == material_id).first()
    if not obj:
        raise HTTPException(404, "inventory not found")
    return obj


@router.post("/inventory", response_model=InventoryOut, status_code=201)
def upsert_inventory(data: InventoryCreate, db: Session = Depends(get_db)):
    obj = db.query(Inventory).filter(Inventory.material_id == data.material_id).first()
    if obj:
        obj.on_hand = data.on_hand
        obj.in_transit = data.in_transit
    else:
        obj = Inventory(**data.model_dump())
        db.add(obj)
    db.commit(); db.refresh(obj)
    return obj


@router.get("/scheduled-receipts", response_model=list[ReceiptOut])
def list_receipts(db: Session = Depends(get_db)):
    return db.query(ScheduledReceipt).all()


@router.post("/scheduled-receipts", response_model=ReceiptOut, status_code=201)
def create_receipt(data: ReceiptCreate, db: Session = Depends(get_db)):
    obj = ScheduledReceipt(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.get("/capacity", response_model=list[CapacityOut])
def list_capacity(db: Session = Depends(get_db)):
    return db.query(CapacityRecord).all()


@router.post("/capacity", response_model=CapacityOut, status_code=201)
def upsert_capacity(data: CapacityBase, db: Session = Depends(get_db)):
    obj = db.query(CapacityRecord).filter(CapacityRecord.week == data.week).first()
    if obj:
        obj.capacity_qty = data.capacity_qty
    else:
        obj = CapacityRecord(**data.model_dump())
        db.add(obj)
    db.commit(); db.refresh(obj)
    return obj