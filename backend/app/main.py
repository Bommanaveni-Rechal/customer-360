from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, ensure_action_columns, get_db, get_engine
from app.demo_data import STORY_ORDER
from app.models import AppMeta, Customer
from app.seed import SEED_VERSION, reseed
from app.services.assistant import answer_question
from app.services.engine import ACTION_LABELS, summarize_row
from app.services.llm import llm_configured
from app.services.portfolio import (
    all_details,
    is_churn,
    one_detail,
    reanalyze,
    record_action,
    record_result,
    searchable,
    update_case,
)

PRIORITY_RANK = {"High": 0, "Medium": 1, "Low": 2, "None": 3}


def load_env_files() -> None:
    root = Path(__file__).resolve().parents[2]
    backend = Path(__file__).resolve().parents[1]
    for path in (root / ".env", backend / ".env"):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def init_db() -> None:
    Base.metadata.create_all(bind=get_engine())
    ensure_action_columns()


def ensure_seed() -> None:
    init_db()
    current = None
    count = 0
    db = SessionLocal()
    try:
        try:
            row = db.get(AppMeta, "seed_version")
            current = row.value if row else None
            count = db.query(Customer).count()
        except OperationalError:
            db.rollback()
    finally:
        db.close()
    if current == SEED_VERSION and count > 0:
        return
    Base.metadata.drop_all(bind=get_engine())
    Base.metadata.create_all(bind=get_engine())
    db = SessionLocal()
    try:
        reseed(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    load_env_files()
    ensure_seed()
    yield


app = FastAPI(
    title="Customer-360 API",
    version="1.0.0",
    description="Customer 360 and next best action for an insurance and lending book. "
    "Transcript readings and answers use a rules engine unless OPENAI_API_KEY is set.",
    lifespan=lifespan,
)

load_env_files()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)


class ActionIn(BaseModel):
    action_type: str = Field(min_length=2, max_length=64)
    title: str = Field(min_length=2, max_length=180)
    outcome: str = Field(pattern="^(Completed|Scheduled|Dismissed)$")
    note: str = Field(default="", max_length=2000)
    owner: str = Field(default="", max_length=80)
    due_on: str | None = None
    priority: str = Field(default="", max_length=16)
    result: str = Field(default="", max_length=40)


class ResultIn(BaseModel):
    result: str = Field(pattern="^(Customer retained|Complaint resolved|Renewal completed|Customer declined|No response)$")


class CaseIn(BaseModel):
    status: str = Field(pattern="^(Open|In Progress|Resolved|Denied)$")


def _rows(db: Session) -> list[dict]:
    details = all_details(db)
    rows = []
    for detail in details:
        row = summarize_row(detail)
        row["_search"] = searchable(detail)
        row["_detail_priority"] = detail["nba"]["priority"]
        rows.append(row)
    return rows


def _sort_rows(rows: list[dict], sort: str) -> list[dict]:
    if sort == "risk":
        return sorted(rows, key=lambda row: (-row["risk_score"], row["name"]))
    if sort == "value":
        return sorted(rows, key=lambda row: (-row["customer_value"], row["name"]))
    if sort == "name":
        return sorted(rows, key=lambda row: row["name"])
    return sorted(rows, key=lambda row: (PRIORITY_RANK.get(row["nba"]["priority"], 9), -row["risk_score"], row["name"]))


def _public_row(row: dict) -> dict:
    return {key: value for key, value in row.items() if not key.startswith("_")}


@app.get("/")
def root():
    return {
        "service": "Customer-360 API",
        "docs": "/docs",
        "health": "/api/health",
        "frontend": "http://localhost:5173",
    }


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    return {
        "status": "ok",
        "ai_mode": "llm" if llm_configured() else "rules",
        "customers": db.query(Customer).count(),
        "seed_version": SEED_VERSION,
    }


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    details = all_details(db)
    rows = [summarize_row(detail) for detail in details]
    by_id = {row["id"]: row for row in rows}

    def series(labels: list[str], key: str) -> list[dict]:
        counts = {label: 0 for label in labels}
        for row in rows:
            label = row[key]
            if label not in counts:
                counts[label] = 0
            counts[label] += 1
        return [{"label": label, "value": counts[label]} for label in counts]

    action_counts: dict[str, int] = {}
    for row in rows:
        label = ACTION_LABELS.get(row["nba"]["action_type"], row["nba"]["action_type"])
        action_counts[label] = action_counts.get(label, 0) + 1
    actions = [{"label": label, "value": value} for label, value in sorted(action_counts.items(), key=lambda item: (-item[1], item[0]))]

    queue = [row for row in rows if row["nba"]["action_type"] != "no_action"]
    queue.sort(key=lambda row: (PRIORITY_RANK.get(row["nba"]["priority"], 9), -row["risk_score"], row["name"]))
    return {
        "ai_mode": "llm" if llm_configured() else "rules",
        "kpis": {
            "customers": len(rows),
            "high_risk": sum(1 for row in rows if row["risk_level"] == "High"),
            "needs_action": sum(1 for row in rows if row["nba"]["priority"] in {"High", "Medium"}),
            "negative_sentiment": sum(1 for row in rows if row["sentiment"] == "Negative"),
            "open_issues": sum(row["open_issues"] for row in rows),
            "churn_cases": sum(1 for detail in details if is_churn(detail)),
            "recommended_actions": len(queue),
        },
        "charts": {
            "sentiment": series(["Positive", "Neutral", "Negative"], "sentiment"),
            "risk": series(["High", "Medium", "Low"], "risk_level"),
            "segments": series(["Priority", "Affluent", "Retail", "Mass", "SME"], "segment"),
            "actions": actions,
        },
        "stories": [by_id[story_id] for story_id in STORY_ORDER if story_id in by_id],
        "queue": queue,
    }


@app.get("/api/customers")
def customers(
    q: str = "",
    risk: str = "",
    sentiment: str = "",
    book: str = "",
    segment: str = "",
    needs_action: bool = False,
    churn: bool = False,
    open_issue: bool = False,
    sort: str = Query(default="priority"),
    db: Session = Depends(get_db),
):
    rows = _rows(db)
    if q.strip():
        needle = q.strip().lower()
        rows = [row for row in rows if needle in row["_search"]]
    if risk:
        rows = [row for row in rows if row["risk_level"] == risk]
    if sentiment:
        rows = [row for row in rows if row["sentiment"] == sentiment]
    if book:
        rows = [row for row in rows if row["book"] == book]
    if segment:
        rows = [row for row in rows if row["segment"] == segment]
    if needs_action:
        rows = [row for row in rows if row["nba"]["priority"] in {"High", "Medium"}]
    if churn:
        rows = [row for row in rows if row["churn_probability"] >= 0.45]
    if open_issue:
        rows = [row for row in rows if row["open_issues"] > 0]
    return {"customers": [_public_row(row) for row in _sort_rows(rows, sort)]}


@app.get("/api/customers/{customer_id}")
def customer_detail(customer_id: str, db: Session = Depends(get_db)):
    detail = one_detail(db, customer_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Customer not found")
    return detail


@app.post("/api/customers/{customer_id}/analyze")
def analyze_customer(customer_id: str, db: Session = Depends(get_db)):
    detail = reanalyze(db, customer_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Customer not found")
    return detail


@app.post("/api/customers/{customer_id}/ask")
def ask_customer(customer_id: str, body: AskIn, db: Session = Depends(get_db)):
    detail = one_detail(db, customer_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Customer not found")
    return answer_question(body.question.strip(), detail)


@app.post("/api/customers/{customer_id}/actions")
def take_action(customer_id: str, body: ActionIn, db: Session = Depends(get_db)):
    detail = record_action(
        db,
        customer_id,
        body.action_type,
        body.title,
        body.outcome,
        body.note,
        owner=body.owner,
        due_on=body.due_on,
        priority=body.priority,
        result=body.result,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if detail == "bad_result":
        raise HTTPException(status_code=422, detail="Unknown action outcome")
    return detail


@app.post("/api/actions/{action_id}/result")
def take_result(action_id: int, body: ResultIn, db: Session = Depends(get_db)):
    detail = record_result(db, action_id, body.result)
    if detail is None:
        raise HTTPException(status_code=404, detail="Action not found")
    if detail == "not_completed":
        raise HTTPException(status_code=409, detail="Record an outcome after the action is completed")
    return detail


@app.patch("/api/cases/{case_id}")
def patch_case(case_id: str, body: CaseIn, db: Session = Depends(get_db)):
    detail = update_case(db, case_id, body.status)
    if not detail:
        raise HTTPException(status_code=404, detail="Case not found")
    return detail


@app.get("/api/actions")
def action_queue(db: Session = Depends(get_db)):
    rows = [summarize_row(detail) for detail in all_details(db) if detail["nba"]["action_type"] != "no_action"]
    rows.sort(key=lambda row: (PRIORITY_RANK.get(row["nba"]["priority"], 9), -row["risk_score"], row["name"]))
    return {"actions": rows}


@app.post("/api/demo/reset")
def reset_demo():
    Base.metadata.drop_all(bind=get_engine())
    Base.metadata.create_all(bind=get_engine())
    db = SessionLocal()
    try:
        reseed(db)
        count = db.query(Customer).count()
    finally:
        db.close()
    return {"ok": True, "customers": count, "seed_version": SEED_VERSION}
