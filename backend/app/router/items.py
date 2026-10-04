"""主数据 CRUD：products / materials / bom / suppliers。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_roles
from ..database import get_db
from ..models import BOMMapping, Material, Product, Supplier
from ..schemas import (
    BOMCreate,
    BOMOut,
    MaterialCreate,
    MaterialOut,
    ProductCreate,
    ProductOut,
    SupplierCreate,
    SupplierOut,
)

router = APIRouter(prefix="/api", tags=["items"])


def _material_out(m: Material) -> MaterialOut:
    return MaterialOut(
        id=m.id, code=m.code, name=m.name, type=m.type, cost=float(m.cost),
        lead_days=m.lead_days, supplier_id=m.supplier_id,
        safety_stock=m.safety_stock, on_hand=m.on_hand, critical=m.critical,
        supplier_name=m.supplier.name if m.supplier else None,
    )


# ---- Product ----
@router.get("/products", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db)):
    return db.query(Product).all()


@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(data: ProductCreate, db: Session = Depends(get_db)):
    obj = Product(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.get("/products/{item_id}", response_model=ProductOut)
def get_product(item_id: str, db: Session = Depends(get_db)):
    obj = db.get(Product, item_id)
    if not obj:
        raise HTTPException(404, "product not found")
    return obj


@router.put("/products/{item_id}", response_model=ProductOut)
def update_product(item_id: str, data: ProductCreate, db: Session = Depends(get_db)):
    obj = db.get(Product, item_id)
    if not obj:
        raise HTTPException(404, "product not found")
    for k, v in data.model_dump().items():
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/products/{item_id}", status_code=204)
def delete_product(item_id: str, db: Session = Depends(get_db),
                   _u: dict = Depends(require_roles("admin"))):
    obj = db.get(Product, item_id)
    if not obj:
        raise HTTPException(404, "product not found")
    db.delete(obj); db.commit()


# ---- Material ----
@router.get("/materials", response_model=list[MaterialOut])
def list_materials(db: Session = Depends(get_db)):
    return [_material_out(m) for m in db.query(Material).all()]


@router.post("/materials", response_model=MaterialOut, status_code=201)
def create_material(data: MaterialCreate, db: Session = Depends(get_db)):
    obj = Material(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return _material_out(obj)


@router.get("/materials/{item_id}", response_model=MaterialOut)
def get_material(item_id: str, db: Session = Depends(get_db)):
    obj = db.get(Material, item_id)
    if not obj:
        raise HTTPException(404, "material not found")
    return _material_out(obj)


@router.put("/materials/{item_id}", response_model=MaterialOut)
def update_material(item_id: str, data: MaterialCreate, db: Session = Depends(get_db)):
    obj = db.get(Material, item_id)
    if not obj:
        raise HTTPException(404, "material not found")
    for k, v in data.model_dump().items():
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return _material_out(obj)


@router.delete("/materials/{item_id}", status_code=204)
def delete_material(item_id: str, db: Session = Depends(get_db),
                    _u: dict = Depends(require_roles("admin"))):
    obj = db.get(Material, item_id)
    if not obj:
        raise HTTPException(404, "material not found")
    db.delete(obj); db.commit()


# ---- BOM ----
@router.get("/bom", response_model=list[BOMOut])
def list_bom(db: Session = Depends(get_db)):
    return db.query(BOMMapping).all()


@router.get("/products/{item_id}/bom", response_model=list[BOMOut])
def product_bom(item_id: str, db: Session = Depends(get_db)):
    return db.query(BOMMapping).filter(BOMMapping.product_id == item_id).all()


@router.post("/bom", response_model=BOMOut, status_code=201)
def create_bom(data: BOMCreate, db: Session = Depends(get_db)):
    obj = BOMMapping(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.delete("/bom/{item_id}", status_code=204)
def delete_bom(item_id: str, db: Session = Depends(get_db)):
    obj = db.get(BOMMapping, item_id)
    if not obj:
        raise HTTPException(404, "bom not found")
    db.delete(obj); db.commit()


# ---- Supplier ----
@router.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(db: Session = Depends(get_db)):
    return db.query(Supplier).all()


@router.post("/suppliers", response_model=SupplierOut, status_code=201)
def create_supplier(data: SupplierCreate, db: Session = Depends(get_db)):
    obj = Supplier(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.put("/suppliers/{item_id}", response_model=SupplierOut)
def update_supplier(item_id: str, data: SupplierCreate, db: Session = Depends(get_db)):
    obj = db.get(Supplier, item_id)
    if not obj:
        raise HTTPException(404, "supplier not found")
    for k, v in data.model_dump().items():
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/suppliers/{item_id}", status_code=204)
def delete_supplier(item_id: str, db: Session = Depends(get_db)):
    obj = db.get(Supplier, item_id)
    if not obj:
        raise HTTPException(404, "supplier not found")
    db.delete(obj); db.commit()