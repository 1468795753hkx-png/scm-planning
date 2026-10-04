"""Pydantic 序列化/校验 schema（v2 风格）。"""
from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Supplier ----
class SupplierBase(BaseModel):
    name: str
    lead_time_days: int = 0
    capacity: int = 0
    reliability: Optional[float] = 1.0


class SupplierCreate(SupplierBase):
    pass


class SupplierOut(SupplierBase, ORMModel):
    id: str


# ---- Product ----
class ProductBase(BaseModel):
    code: str
    name: str
    unit_cost: Optional[float] = 0
    active: Optional[bool] = True


class ProductCreate(ProductBase):
    pass


class ProductOut(ProductBase, ORMModel):
    id: str


# ---- Material ----
class MaterialBase(BaseModel):
    code: str
    name: str
    type: Optional[str] = "Comp"
    cost: Optional[float] = 0
    lead_days: Optional[int] = 7
    supplier_id: Optional[str] = None
    safety_stock: Optional[int] = 0
    on_hand: Optional[int] = 0
    critical: Optional[bool] = False


class MaterialCreate(MaterialBase):
    pass


class MaterialOut(MaterialBase, ORMModel):
    id: str
    supplier_name: Optional[str] = None


# ---- BOM ----
class BOMBase(BaseModel):
    product_id: str
    material_id: str
    qty: int = 1


class BOMCreate(BOMBase):
    pass


class BOMOut(BOMBase, ORMModel):
    id: str


# ---- Order ----
class OrderBase(BaseModel):
    product_id: str
    week: int
    qty: int


class OrderCreate(OrderBase):
    pass


class OrderOut(OrderBase, ORMModel):
    id: str


# ---- ForecastHistory ----
class HistoryBase(BaseModel):
    product_id: str
    period: date
    qty: int


class HistoryCreate(HistoryBase):
    pass


class HistoryOut(HistoryBase, ORMModel):
    id: str


# ---- Inventory ----
class InventoryBase(BaseModel):
    material_id: str
    on_hand: int = 0
    in_transit: int = 0


class InventoryCreate(InventoryBase):
    pass


class InventoryOut(InventoryBase, ORMModel):
    id: str


# ---- ScheduledReceipt ----
class ReceiptBase(BaseModel):
    material_id: str
    week: int
    qty: int


class ReceiptCreate(ReceiptBase):
    pass


class ReceiptOut(ReceiptBase, ORMModel):
    id: str


# ---- Capacity ----
class CapacityBase(BaseModel):
    week: int
    capacity_qty: int = 2900


class CapacityOut(CapacityBase, ORMModel):
    id: str


# ---- PlanRun ----
class PlanRunOut(ORMModel):
    id: str
    created_at: object
    method: str
    input: Optional[dict] = None
    output: Optional[dict] = None


# ---- PurchaseOrder ----
class PurchaseOrderOut(ORMModel):
    id: str
    po_no: str
    run_id: Optional[str] = None
    material_id: str
    supplier_id: Optional[str] = None
    qty: int
    order_week: int
    arrival_week: int
    amount: float
    status: str
    reason: Optional[str] = None


# ---- Request bodies for plan ----
class ForecastRequest(BaseModel):
    product_ids: Optional[list[str]] = None
    horizon_weeks: int = 4
    use_forecast: bool = True


class PlanRunRequest(BaseModel):
    use_forecast: bool = False
    mult: float = 1.0
    capacity_week: int = 2900
    optimize_method: str = "heuristic"  # heuristic | milp
    auto_cap: float = 30000.0


class POGenerateRequest(BaseModel):
    run_id: str
    auto_cap: float = 30000.0