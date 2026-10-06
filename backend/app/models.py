from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    age: Mapped[int] = mapped_column(Integer)
    city: Mapped[str] = mapped_column(String(80))
    region: Mapped[str] = mapped_column(String(80))
    occupation: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(40))
    segment: Mapped[str] = mapped_column(String(32))
    book: Mapped[str] = mapped_column(String(32))
    tenure_months: Mapped[int] = mapped_column(Integer)
    customer_value: Mapped[float] = mapped_column(Float)
    joined_on: Mapped[date] = mapped_column(Date)
    story_kicker: Mapped[str | None] = mapped_column(String(80), nullable=True)
    story_title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    story_blurb: Mapped[str | None] = mapped_column(String(320), nullable=True)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(120))
    number: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    installment: Mapped[float] = mapped_column(Float)
    frequency: Mapped[str] = mapped_column(String(16))
    cover: Mapped[float] = mapped_column(Float, default=0)
    outstanding: Mapped[float] = mapped_column(Float, default=0)
    renewal_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    started_on: Mapped[date] = mapped_column(Date)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    paid_on: Mapped[date] = mapped_column(Date)
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16))


class ServiceCase(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24))
    opened_on: Mapped[date] = mapped_column(Date)
    closed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    channel: Mapped[str] = mapped_column(String(16))
    direction: Mapped[str] = mapped_column(String(16))
    occurred_on: Mapped[datetime] = mapped_column(DateTime)
    agent: Mapped[str] = mapped_column(String(80))
    subject: Mapped[str] = mapped_column(String(180))
    body: Mapped[str] = mapped_column(Text)
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sentiment: Mapped[str] = mapped_column(String(16), default="Neutral")
    intent: Mapped[str] = mapped_column(String(80), default="General service")
    topics: Mapped[str] = mapped_column(Text, default="[]")
    concerns: Mapped[str] = mapped_column(Text, default="[]")
    urgency: Mapped[str] = mapped_column(String(16), default="Low")
    entities: Mapped[str] = mapped_column(Text, default="[]")
    churn_signals: Mapped[str] = mapped_column(Text, default="[]")
    summary: Mapped[str] = mapped_column(Text, default="")
    quote: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(16), default="rules")


class ActionLog(Base):
    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    action_type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(180))
    outcome: Mapped[str] = mapped_column(String(24))
    note: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(80), default="")
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(16), default="")
    result: Mapped[str] = mapped_column(String(40), default="")
    risk_before: Mapped[str] = mapped_column(String(16), default="")
    risk_after: Mapped[str] = mapped_column(String(16), default="")
    nba_before: Mapped[str] = mapped_column(String(180), default="")
    nba_after: Mapped[str] = mapped_column(String(180), default="")
    created_on: Mapped[datetime] = mapped_column(DateTime)


class AppMeta(Base):
    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(120))
