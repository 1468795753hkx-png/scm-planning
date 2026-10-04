"""ORM 模型（对应 SPEC 4.2 的 ER；主键用可移植的字符串 UUID）。"""
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


def _uid() -> str:
    return str(uuid.uuid4())


class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(String(36), primary_key=True, default=_uid)
    name = Column(String(200), nullable=False)
    lead_time_days = Column(Integer, nullable=False, default=0)
    capacity = Column(Integer, nullable=False, default=0)
    reliability = Column(Numeric(6, 4), nullable=False, default=1)

    materials = relationship("Material", back_populates="supplier")


class Product(Base):
    __tablename__ = "products"
    id = Column(String(36), primary_key=True, default=_uid)
    code = Column(String(50), unique=True, nullable=False)  # P-A
    name = Column(String(200), nullable=False)
    unit_cost = Column(Numeric(14, 2), nullable=False, default=0)
    active = Column(Boolean, nullable=False, default=True)

    orders = relationship("Order", back_populates="product")
    bom = relationship("BOMMapping", back_populates="product")


class Material(Base):
    __tablename__ = "materials"
    id = Column(String(36), primary_key=True, default=_uid)
    code = Column(String(50), unique=True, nullable=False)  # M001
    name = Column(String(200), nullable=False)
    type = Column(String(20), nullable=False, default="Comp")  # Raw / Comp
    cost = Column(Numeric(14, 2), nullable=False, default=0)
    lead_days = Column(Integer, nullable=False, default=7)
    supplier_id = Column(String(36), ForeignKey("suppliers.id"), nullable=True)
    safety_stock = Column(Integer, nullable=False, default=0)
    on_hand = Column(Integer, nullable=False, default=0)
    critical = Column(Boolean, nullable=False, default=False)  # 关键长交期件

    supplier = relationship("Supplier", back_populates="materials")
    bom = relationship("BOMMapping", back_populates="material")
    inventory = relationship("Inventory", back_populates="material", uselist=False)
    receipts = relationship("ScheduledReceipt", back_populates="material")


class BOMMapping(Base):
    __tablename__ = "bom"
    __table_args__ = (UniqueConstraint("product_id", "material_id", name="uq_bom"),)
    id = Column(String(36), primary_key=True, default=_uid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False)
    material_id = Column(String(36), ForeignKey("materials.id"), nullable=False)
    qty = Column(Integer, nullable=False, default=1)

    product = relationship("Product", back_populates="bom")
    material = relationship("Material", back_populates="bom")


class Order(Base):
    __tablename__ = "orders"
    id = Column(String(36), primary_key=True, default=_uid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False)
    week = Column(Integer, nullable=False)
    qty = Column(Integer, nullable=False)

    product = relationship("Product", back_populates="orders")


class ForecastHistory(Base):
    __tablename__ = "forecast_history"
    id = Column(String(36), primary_key=True, default=_uid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False)
    period = Column(Date, nullable=False)
    qty = Column(Integer, nullable=False)


class Inventory(Base):
    __tablename__ = "inventory"
    id = Column(String(36), primary_key=True, default=_uid)
    material_id = Column(String(36), ForeignKey("materials.id"), nullable=False)
    on_hand = Column(Integer, nullable=False, default=0)
    in_transit = Column(Integer, nullable=False, default=0)

    material = relationship("Material", back_populates="inventory")


class ScheduledReceipt(Base):
    __tablename__ = "scheduled_receipts"
    id = Column(String(36), primary_key=True, default=_uid)
    material_id = Column(String(36), ForeignKey("materials.id"), nullable=False)
    week = Column(Integer, nullable=False)
    qty = Column(Integer, nullable=False)

    material = relationship("Material", back_populates="receipts")


class CapacityRecord(Base):
    __tablename__ = "capacity"
    id = Column(String(36), primary_key=True, default=_uid)
    week = Column(Integer, nullable=False)
    capacity_qty = Column(Integer, nullable=False, default=2900)


class PlanRun(Base):
    __tablename__ = "plan_runs"
    id = Column(String(36), primary_key=True, default=_uid)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    method = Column(String(30), nullable=False, default="heuristic")
    input = Column(JSON, nullable=True)
    output = Column(JSON, nullable=True)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id = Column(String(36), primary_key=True, default=_uid)
    po_no = Column(String(60), unique=True, nullable=False)
    run_id = Column(String(36), ForeignKey("plan_runs.id"), nullable=True)
    material_id = Column(String(36), ForeignKey("materials.id"), nullable=False)
    supplier_id = Column(String(36), ForeignKey("suppliers.id"), nullable=True)
    qty = Column(Integer, nullable=False)
    order_week = Column(Integer, nullable=False)
    arrival_week = Column(Integer, nullable=False)
    amount = Column(Numeric(16, 2), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # auto|pending|approved|rejected
    reason = Column(Text, nullable=True)

    material = relationship("Material")


class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=_uid)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(20), nullable=False, default="viewer")  # admin | planner | viewer