from __future__ import annotations

import json
from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from app.demo_data import CUSTOMERS
from app.models import ActionLog, AppMeta, Customer, Interaction, Payment, Product, ServiceCase
from app.services.nlp import analyze_text

SEED_VERSION = "2026.10.2"


def payment_plan(spec: str) -> list[tuple[int, str]]:
    if spec == "monthly6":
        return [(30 * month, "Paid") for month in range(1, 7)]
    if spec == "monthly6-late-2":
        return [(30 * month, "Late" if month == 2 else "Paid") for month in range(1, 7)]
    if spec == "monthly6-miss-1":
        return [(30 * month, "Missed" if month == 1 else "Paid") for month in range(1, 7)]
    if spec == "monthly6-miss-1-2":
        return [(30 * month, "Missed" if month in {1, 2} else "Paid") for month in range(1, 7)]
    if spec == "annual2":
        return [(20, "Paid"), (385, "Paid")]
    if spec == "lapsed":
        return [(30 * month, "Missed" if month <= 3 else "Paid") for month in range(1, 7)]
    raise ValueError(f"Unknown payment spec: {spec}")


def reseed(db: Session, today=None) -> None:
    today = today or datetime.now().date()
    for model in (ActionLog, Interaction, Payment, ServiceCase, Product, Customer, AppMeta):
        db.query(model).delete()
    db.flush()

    for raw in CUSTOMERS:
        joined = today - timedelta(days=raw["tenure_months"] * 30)
        db.add(
            Customer(
                id=raw["id"],
                name=raw["name"],
                age=raw["age"],
                city=raw["city"],
                region=raw["region"],
                occupation=raw["occupation"],
                email=raw["email"],
                phone=raw["phone"],
                segment=raw["segment"],
                book=raw["book"],
                tenure_months=raw["tenure_months"],
                customer_value=raw["customer_value"],
                joined_on=joined,
                story_kicker=raw.get("story_kicker"),
                story_title=raw.get("story_title"),
                story_blurb=raw.get("story_blurb"),
            )
        )
        db.flush()

        product_rows: list[Product] = []
        for spec in raw["products"]:
            renewal_in = spec.get("renewal_in_days")
            status = spec["status"]
            if status == "Active" and spec["kind"] == "Policy" and renewal_in is not None and 0 <= renewal_in <= 30:
                status = "Pending Renewal"
            started_days = spec.get("started_days_ago", raw["tenure_months"] * 30)
            product = Product(
                customer_id=raw["id"],
                kind=spec["kind"],
                name=spec["name"],
                number=spec["number"],
                status=status,
                installment=spec["installment"],
                frequency=spec["frequency"],
                cover=spec.get("cover") or 0,
                outstanding=spec.get("outstanding") or 0,
                renewal_on=None if renewal_in is None else today + timedelta(days=renewal_in),
                next_due_on=None if status == "Lapsed" else today + timedelta(days=spec.get("next_due_days", 14)),
                started_on=today - timedelta(days=started_days),
            )
            db.add(product)
            db.flush()
            product_rows.append(product)
            for offset, pay_status in payment_plan(spec["pay"]):
                if offset > started_days + 3:
                    continue
                db.add(
                    Payment(
                        customer_id=raw["id"],
                        product_id=product.id,
                        paid_on=today - timedelta(days=offset),
                        amount=spec["installment"],
                        status=pay_status,
                    )
                )

        case_rows: list[ServiceCase] = []
        for spec in raw["cases"]:
            product = product_rows[spec["product_index"]] if spec.get("product_index") is not None else None
            closed_days = spec.get("closed_days_ago")
            case = ServiceCase(
                id=spec["id"],
                customer_id=raw["id"],
                product_id=product.id if product else None,
                kind=spec["kind"],
                title=spec["title"],
                description=spec["description"],
                status=spec["status"],
                opened_on=today - timedelta(days=spec["opened_days_ago"]),
                closed_on=None if closed_days is None else today - timedelta(days=closed_days),
                amount=spec.get("amount"),
            )
            db.add(case)
            case_rows.append(case)

        catalog = [product.number for product in product_rows] + [product.name for product in product_rows] + [case.id for case in case_rows]
        for index, spec in enumerate(raw["interactions"]):
            reading = analyze_text(spec["body"], catalog)
            hour = 15 if spec["channel"] == "Call" else 11
            occurred = datetime.combine(today - timedelta(days=spec["days_ago"]), time(hour, (index * 7) % 50))
            db.add(
                Interaction(
                    customer_id=raw["id"],
                    channel=spec["channel"],
                    direction=spec["direction"],
                    occurred_on=occurred,
                    agent=spec["agent"],
                    subject=spec["subject"],
                    body=spec["body"],
                    duration_min=spec.get("duration_min"),
                    sentiment=reading["sentiment"],
                    intent=reading["intent"],
                    topics=json.dumps(reading["topics"]),
                    concerns=json.dumps(reading["concerns"]),
                    urgency=reading["urgency"],
                    entities=json.dumps(reading["entities"]),
                    churn_signals=json.dumps(reading["churn_signals"]),
                    summary=reading["summary"],
                    quote=reading["quote"],
                    source=reading["source"],
                )
            )

    db.add(AppMeta(key="seed_version", value=SEED_VERSION))
    db.commit()
