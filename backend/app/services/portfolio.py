from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import ActionLog, Customer, Interaction, Payment, Product, ServiceCase
from app.services.engine import CHURN_CUTOFF, build_customer
from app.services.llm import analyze_with_fallback


def _loads(value: str | None) -> list:
    try:
        data = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _iso_date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _iso_dt(value: datetime | None) -> str | None:
    return value.isoformat(timespec="minutes") if value else None


def _assemble(customer: Customer, products, payments, cases, interactions, actions) -> dict:
    product_by_id = {product.id: product for product in products}
    return {
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "age": customer.age,
            "city": customer.city,
            "region": customer.region,
            "occupation": customer.occupation,
            "email": customer.email,
            "phone": customer.phone,
            "segment": customer.segment,
            "book": customer.book,
            "tenure_months": customer.tenure_months,
            "customer_value": customer.customer_value,
            "joined_on": _iso_date(customer.joined_on),
            "story_kicker": customer.story_kicker,
            "story_title": customer.story_title,
            "story_blurb": customer.story_blurb,
        },
        "products": [
            {
                "id": product.id,
                "kind": product.kind,
                "name": product.name,
                "number": product.number,
                "status": product.status,
                "installment": product.installment,
                "frequency": product.frequency,
                "cover": product.cover,
                "outstanding": product.outstanding,
                "renewal_on": _iso_date(product.renewal_on),
                "next_due_on": _iso_date(product.next_due_on),
                "started_on": _iso_date(product.started_on),
            }
            for product in products
        ],
        "payments": [
            {
                "id": payment.id,
                "product_name": product_by_id[payment.product_id].name,
                "product_number": product_by_id[payment.product_id].number,
                "paid_on": _iso_date(payment.paid_on),
                "amount": payment.amount,
                "status": payment.status,
            }
            for payment in payments
            if payment.product_id in product_by_id
        ],
        "cases": [
            {
                "id": case.id,
                "kind": case.kind,
                "title": case.title,
                "description": case.description,
                "status": case.status,
                "opened_on": _iso_date(case.opened_on),
                "closed_on": _iso_date(case.closed_on),
                "amount": case.amount,
                "product_name": product_by_id[case.product_id].name if case.product_id in product_by_id else None,
            }
            for case in cases
        ],
        "interactions": [
            {
                "id": item.id,
                "channel": item.channel,
                "direction": item.direction,
                "occurred_on": _iso_dt(item.occurred_on),
                "agent": item.agent,
                "subject": item.subject,
                "body": item.body,
                "duration_min": item.duration_min,
                "sentiment": item.sentiment,
                "intent": item.intent,
                "topics": _loads(item.topics),
                "concerns": _loads(item.concerns),
                "urgency": item.urgency,
                "entities": _loads(item.entities),
                "churn_signals": _loads(item.churn_signals),
                "summary": item.summary,
                "quote": item.quote,
                "source": item.source,
            }
            for item in interactions
        ],
        "actions": [_action_payload(action) for action in actions],
    }


def all_details(db: Session) -> list[dict]:
    customers = db.query(Customer).all()
    grouped_products = defaultdict(list)
    grouped_payments = defaultdict(list)
    grouped_cases = defaultdict(list)
    grouped_interactions = defaultdict(list)
    grouped_actions = defaultdict(list)
    for row in db.query(Product).all():
        grouped_products[row.customer_id].append(row)
    for row in db.query(Payment).all():
        grouped_payments[row.customer_id].append(row)
    for row in db.query(ServiceCase).all():
        grouped_cases[row.customer_id].append(row)
    for row in db.query(Interaction).all():
        grouped_interactions[row.customer_id].append(row)
    for row in db.query(ActionLog).all():
        grouped_actions[row.customer_id].append(row)
    details = []
    for customer in customers:
        payload = _assemble(
            customer,
            grouped_products[customer.id],
            grouped_payments[customer.id],
            grouped_cases[customer.id],
            grouped_interactions[customer.id],
            grouped_actions[customer.id],
        )
        details.append(build_customer(payload))
    return details


def one_detail(db: Session, customer_id: str) -> dict | None:
    customer = db.get(Customer, customer_id)
    if not customer:
        return None
    payload = _assemble(
        customer,
        db.query(Product).filter_by(customer_id=customer_id).all(),
        db.query(Payment).filter_by(customer_id=customer_id).all(),
        db.query(ServiceCase).filter_by(customer_id=customer_id).all(),
        db.query(Interaction).filter_by(customer_id=customer_id).all(),
        db.query(ActionLog).filter_by(customer_id=customer_id).all(),
    )
    return build_customer(payload)


def searchable(detail: dict) -> str:
    parts = [
        detail["customer"]["name"],
        detail["customer"]["id"],
        detail["customer"]["city"],
        detail["customer"]["region"],
        detail["customer"]["occupation"],
        detail["customer"]["segment"],
        detail["customer"]["book"],
        detail["headline_product"],
        detail["nba"]["title"],
    ]
    parts.extend(f"{product['name']} {product['number']}" for product in detail["products"])
    parts.extend(f"{case['id']} {case['title']}" for case in detail["cases"])
    return " ".join(parts).lower()


def reanalyze(db: Session, customer_id: str) -> dict | None:
    customer = db.get(Customer, customer_id)
    if not customer:
        return None
    products = db.query(Product).filter_by(customer_id=customer_id).all()
    cases = db.query(ServiceCase).filter_by(customer_id=customer_id).all()
    catalog = [product.number for product in products] + [product.name for product in products] + [case.id for case in cases]
    for item in db.query(Interaction).filter_by(customer_id=customer_id).all():
        reading = analyze_with_fallback(item.body, catalog, allow_llm=True)
        item.sentiment = reading["sentiment"]
        item.intent = reading["intent"]
        item.topics = json.dumps(reading["topics"])
        item.concerns = json.dumps(reading["concerns"])
        item.urgency = reading["urgency"]
        item.entities = json.dumps(reading["entities"])
        item.churn_signals = json.dumps(reading["churn_signals"])
        item.summary = reading["summary"]
        item.quote = reading["quote"]
        item.source = reading["source"]
    db.commit()
    return one_detail(db, customer_id)


ALLOWED_RESULTS = {
    "Customer retained",
    "Complaint resolved",
    "Renewal completed",
    "Customer declined",
    "No response",
}
OPEN_CASE = {"Open", "In Progress"}


def _action_payload(action: ActionLog) -> dict:
    return {
        "id": action.id,
        "action_type": action.action_type,
        "title": action.title,
        "outcome": action.outcome,
        "note": action.note or "",
        "owner": action.owner or "",
        "due_on": _iso_date(action.due_on),
        "priority": action.priority or "",
        "result": action.result or "",
        "risk_before": action.risk_before or "",
        "risk_after": action.risk_after or "",
        "nba_before": action.nba_before or "",
        "nba_after": action.nba_after or "",
        "created_on": _iso_dt(action.created_on),
    }


def _parse_due(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value[:10])


def _mutate_for_result(db: Session, customer_id: str, result: str) -> None:
    today = date.today()
    if result == "Complaint resolved":
        for case in db.query(ServiceCase).filter_by(customer_id=customer_id).all():
            if case.kind == "Complaint" and case.status in OPEN_CASE:
                case.status = "Resolved"
                case.closed_on = today
    elif result == "Renewal completed":
        policies = [
            product
            for product in db.query(Product).filter_by(customer_id=customer_id).all()
            if product.kind == "Policy" and product.status != "Lapsed" and product.renewal_on
        ]
        if policies:
            nearest = min(policies, key=lambda product: product.renewal_on)
            nearest.renewal_on = nearest.renewal_on + timedelta(days=365)
            if nearest.status == "Pending Renewal":
                nearest.status = "Active"


def _stamp_shift(db: Session, action: ActionLog, before: dict) -> dict:
    db.commit()
    after = one_detail(db, action.customer_id)
    action.risk_before = before["risk"]["level"]
    action.risk_after = after["risk"]["level"]
    action.nba_before = before["nba"]["title"]
    action.nba_after = after["nba"]["title"]
    db.commit()
    return one_detail(db, action.customer_id)


def record_action(
    db: Session,
    customer_id: str,
    action_type: str,
    title: str,
    outcome: str,
    note: str,
    owner: str = "",
    due_on: str | None = None,
    priority: str = "",
    result: str = "",
) -> dict | str | None:
    if not db.get(Customer, customer_id):
        return None
    cleaned = (result or "").strip()
    if cleaned and cleaned not in ALLOWED_RESULTS:
        return "bad_result"
    if outcome != "Completed":
        cleaned = ""
    before = one_detail(db, customer_id) if cleaned else None
    action = ActionLog(
        customer_id=customer_id,
        action_type=action_type,
        title=title,
        outcome=outcome,
        note=note.strip(),
        owner=owner.strip(),
        due_on=_parse_due(due_on),
        priority=priority.strip(),
        result="",
        created_on=datetime.now().replace(microsecond=0),
    )
    db.add(action)
    db.flush()
    if cleaned and before:
        _mutate_for_result(db, customer_id, cleaned)
        action.result = cleaned
        return _stamp_shift(db, action, before)
    db.commit()
    return one_detail(db, customer_id)


def record_result(db: Session, action_id: int, result: str) -> dict | str | None:
    action = db.get(ActionLog, action_id)
    if not action:
        return None
    if action.outcome != "Completed":
        return "not_completed"
    if result not in ALLOWED_RESULTS:
        return "bad_result"
    if action.result:
        action.result = result
        db.commit()
        return one_detail(db, action.customer_id)
    before = one_detail(db, action.customer_id)
    _mutate_for_result(db, action.customer_id, result)
    action.result = result
    return _stamp_shift(db, action, before)


def update_case(db: Session, case_id: str, status: str) -> dict | None:
    case = db.get(ServiceCase, case_id)
    if not case:
        return None
    case.status = status
    if status in {"Resolved", "Denied"}:
        case.closed_on = date.today()
    else:
        case.closed_on = None
    customer_id = case.customer_id
    db.commit()
    return one_detail(db, customer_id)


def is_churn(detail: dict) -> bool:
    return detail["risk"]["churn_probability"] >= CHURN_CUTOFF
