from __future__ import annotations

from app.services.engine import money
from app.services.llm import answer_with_llm


def answer_question(question: str, view: dict) -> dict:
    modelled = answer_with_llm(question, view)
    if modelled:
        return modelled
    return rules_answer(question, view)


def rules_answer(question: str, view: dict) -> dict:
    customer = view["customer"]
    risk = view["risk"]
    insights = view["insights"]
    nba = view["nba"]
    kind = _kind(question)
    first = customer["name"].split()[0]

    if kind == "risk":
        text = (
            f"{customer['name']} is {risk['level'].lower()} risk, score {risk['score']}, "
            f"with an estimated churn probability of {round(risk['churn_probability'] * 100)}%. "
            + " ".join(risk["factors"])
            + f" Latest sentiment is {insights['sentiment'].lower()} and the intent on file is {insights['intent'].lower()}."
        )
    elif kind == "next":
        text = (
            f"{nba['reason']} Priority is {nba['priority']}. "
            f"Expected impact: {nba['expected_impact']} "
            f"How to do it: {nba['talk_track']}"
        )
    elif kind == "unhappy":
        text = _unhappy(first, view)
    elif kind == "contact":
        if nba["action_type"] == "no_action":
            text = f"No. {nba['reason']}"
        else:
            text = f"Yes. Priority is {nba['priority']}. {nba['reason']}"
    elif kind == "summary":
        recent = []
        for item in view["timeline"][:4]:
            recent.append(f"{item['kind']} — {item['title']}")
        text = insights["summary"]
        if recent:
            text += " Recent file events: " + "; ".join(recent) + "."
    elif kind == "product":
        text = _product(first, view)
    elif kind == "renewal":
        text = _renewal(first, view)
    elif kind == "claim":
        text = _claim(first, view)
    elif kind == "payment":
        text = _payment(first, view)
    else:
        text = f"{insights['summary']} {nba['reason']}"

    if "recommended action:" not in text.lower():
        text = text.rstrip() + f" Recommended action: {nba['title']}."
    return {
        "question": question,
        "answer": text,
        "recommended_action": nba["title"],
        "priority": nba["priority"],
        "source": "rules",
    }


def _kind(question: str) -> str:
    q = question.lower()
    if any(word in q for word in ["risk", "churn", "at risk"]):
        return "risk"
    if any(word in q for word in ["unhappy", "upset", "angry", "frustrat", "disappoint", "negative", "sentiment"]):
        return "unhappy"
    if any(word in q for word in ["contact", "should we call", "reach out", "call them", "call this"]):
        return "contact"
    if any(word in q for word in ["summar", "recent interaction", "what happened"]):
        return "summary"
    if any(word in q for word in ["product", "cross-sell", "cross sell", "relevant", "upsell"]):
        return "product"
    if "renew" in q:
        return "renewal"
    if "claim" in q:
        return "claim"
    if any(word in q for word in ["pay", "emi", "premium", "overdue", "delinquen"]):
        return "payment"
    if any(word in q for word in ["next", "should we", "recommend", "what should", "best action"]):
        return "next"
    return "general"


def _quote_line(view: dict, sentiment: str | None = None) -> str:
    for item in view["timeline"]:
        if not item.get("quote"):
            continue
        if sentiment and item.get("sentiment") != sentiment:
            continue
        return f"On {item['occurred_on'][:10]}, the {item['kind'].lower()} included: “{item['quote']}”"
    return ""


def _unhappy(first: str, view: dict) -> str:
    insights = view["insights"]
    if insights["sentiment"] != "Negative":
        line = _quote_line(view) 
        return (
            f"{first} does not look unhappy. The latest sentiment is {insights['sentiment'].lower()} "
            f"and the intent is {insights['intent'].lower()}. {line}"
        ).strip()
    concerns = "; ".join(insights["concerns"]) if insights["concerns"] else "the file does not name a single concern beyond the tone"
    line = _quote_line(view, "Negative")
    return f"{first} is unhappy in the latest conversation. Concerns on file: {concerns}. {line}".strip()


def _product(first: str, view: dict) -> str:
    nba = view["nba"]
    products = ", ".join(product["name"] for product in view["products"]) or "no active product"
    if nba["action_type"] == "offer_product":
        return f"{nba['reason']} Products already on the file: {products}."
    if nba["action_type"] == "no_action":
        return f"Nothing relevant should be pitched right now. {first} already has {products}. {nba['reason']}"
    return (
        f"A product conversation is not the next step. {nba['reason']} "
        f"Current products: {products}."
    )


def _renewal(first: str, view: dict) -> str:
    upcoming = [
        product
        for product in view["products"]
        if product["kind"] == "Policy" and product.get("renewal_in_days") is not None and product["renewal_in_days"] >= 0
    ]
    if not upcoming:
        lapsed = [product["name"] for product in view["products"] if product["status"] == "Lapsed"]
        if lapsed:
            return f"{', '.join(lapsed)} is already lapsed, so this is a win-back rather than a standard renewal."
        return f"No policy renewal is on the calendar for {first}."
    nearest = min(upcoming, key=lambda product: product["renewal_in_days"])
    return (
        f"{nearest['name']} ({nearest['number']}) renews in {nearest['renewal_in_days']} days. "
        f"Status is {nearest['health'].lower()}."
    )


def _claim(first: str, view: dict) -> str:
    claims = [case for case in view["cases"] if case["kind"] == "Claim"]
    if not claims:
        return f"There is no claim on {first}'s file."
    bits = []
    for case in claims:
        amount = f", {money(case['amount'])}" if case.get("amount") else ""
        bits.append(f"{case['id']} is {case['status'].lower()}{amount} — {case['title']}")
    return "Claims on file: " + "; ".join(bits) + "."


def _payment(first: str, view: dict) -> str:
    missed = [payment for payment in view["payments"] if payment["status"] == "Missed"]
    if not missed:
        last = view["payments"][0] if view["payments"] else None
        if not last:
            return f"No payment ledger is on file for {first}."
        return f"No missed payments are in the recent ledger. The last entry was {last['status'].lower()} for {money(last['amount'])} on {last['paid_on']}."
    total = sum(payment["amount"] for payment in missed)
    return f"{len(missed)} missed payment(s) are on the ledger, totaling {money(total)}."
