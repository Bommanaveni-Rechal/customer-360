from __future__ import annotations

import json
import logging
import os
import re

import httpx

from app.services.nlp import analyze_text

logger = logging.getLogger("customer360.llm")

SENTIMENTS = {"Positive", "Neutral", "Negative"}
URGENCIES = {"Low", "Medium", "High"}


def llm_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def _complete(messages: list[dict], temperature: float = 0.2) -> str | None:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return None
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    try:
        response = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "temperature": temperature, "messages": messages},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception:
        logger.warning("Language model call failed; using the rules engine")
        return None


def _parse_json(content: str) -> dict | None:
    text = content.strip()
    fence = re.search(r"\{.*\}", text, re.DOTALL)
    if not fence:
        return None
    try:
        data = json.loads(fence.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _as_str_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:8]


def analyze_with_fallback(text: str, catalog: list[str], allow_llm: bool = False) -> dict:
    if allow_llm and llm_configured():
        content = _complete(
            [
                {
                    "role": "system",
                    "content": (
                        "You extract insurance and lending service interactions. "
                        "Return only JSON with keys sentiment (Positive, Neutral, or Negative), "
                        "intent, topics, concerns, urgency (Low, Medium, or High), entities, "
                        "churn_signals, summary, quote. Use only facts present in the text. "
                        "quote must be a short verbatim sentence from the text."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"catalog": catalog, "text": text}),
                },
            ]
        )
        parsed = _parse_json(content) if content else None
        if parsed and parsed.get("sentiment") in SENTIMENTS and parsed.get("urgency") in URGENCIES:
            fallback = analyze_text(text, catalog)
            return {
                "sentiment": parsed["sentiment"],
                "intent": str(parsed.get("intent") or fallback["intent"])[:80],
                "topics": _as_str_list(parsed.get("topics")) or fallback["topics"],
                "concerns": _as_str_list(parsed.get("concerns")) or fallback["concerns"],
                "urgency": parsed["urgency"],
                "entities": _as_str_list(parsed.get("entities")) or fallback["entities"],
                "churn_signals": _as_str_list(parsed.get("churn_signals")),
                "summary": str(parsed.get("summary") or fallback["summary"])[:400],
                "quote": str(parsed.get("quote") or fallback["quote"])[:280],
                "source": "llm",
            }
    return analyze_text(text, catalog)


def answer_with_llm(question: str, view: dict) -> dict | None:
    if not llm_configured():
        return None
    nba = view["nba"]
    file_for_model = {
        "customer": view["customer"],
        "risk": view["risk"],
        "insights": view["insights"],
        "recommendation": {
            "action_type": nba["action_type"],
            "title": nba["title"],
            "priority": nba["priority"],
            "reason": nba["reason"],
            "expected_impact": nba["expected_impact"],
            "evidence": nba["evidence"],
            "talk_track": nba["talk_track"],
        },
        "products": [
            {
                "name": product["name"],
                "number": product["number"],
                "kind": product["kind"],
                "status": product["status"],
                "health": product["health"],
                "installment": product["installment"],
                "frequency": product["frequency"],
                "cover": product["cover"],
                "outstanding": product["outstanding"],
                "renewal_in_days": product["renewal_in_days"],
            }
            for product in view["products"]
        ],
        "cases": view["cases"],
        "recent_timeline": [
            {
                "kind": item["kind"],
                "occurred_on": item["occurred_on"],
                "title": item["title"],
                "sentiment": item.get("sentiment"),
                "intent": item.get("intent"),
                "quote": item.get("quote"),
                "detail": (item.get("detail") or "")[:1200],
            }
            for item in view["timeline"][:8]
        ],
    }
    content = _complete(
        [
            {
                "role": "system",
                "content": (
                    "You are Customer-360, an assistant for insurance and lending relationship managers. "
                    "Answer only from the customer file. Be concrete, cite dates, amounts, and quotes that appear in the file, "
                    "and do not invent payments, claims, or conversations. Write plain prose in two short paragraphs. "
                    "End with a line that starts exactly 'Recommended action:' and names a practical next step. "
                    "If the file says no action is required, say that clearly."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({"question": question, "customer_file": file_for_model}),
            },
        ],
        temperature=0.3,
    )
    if not content:
        return None
    answer = content.strip()
    if "recommended action:" not in answer.lower():
        answer = answer.rstrip() + f" Recommended action: {nba['title']}."
    return {
        "question": question,
        "answer": answer,
        "recommended_action": nba["title"],
        "priority": nba["priority"],
        "source": "llm",
    }
