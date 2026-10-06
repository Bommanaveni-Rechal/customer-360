from __future__ import annotations

from datetime import date, datetime

from app.services.nlp import CHURN_PHRASES, REGULATOR_PHRASES, contains

OPEN = {"Open", "In Progress"}
HIGH_VALUE = 40000
CHURN_CUTOFF = 0.45

ENGINE_SELECTION = (
    "The NBA Engine evaluates customer signals, interaction insights, business rules, "
    "and eligibility conditions to select the highest-priority recommended action."
)

RESULT_EFFECT = {
    "Customer retained": (-16, -0.18, "A completed action recorded the customer as retained."),
    "Complaint resolved": (-6, -0.08, "A completed action recorded the complaint as resolved."),
    "Renewal completed": (-6, -0.08, "A completed action recorded the renewal as completed."),
    "Customer declined": (14, 0.16, "The customer declined the recommended action."),
    "No response": (8, 0.08, "There was no response after the recorded action."),
}

ACTION_LABELS = {
    "retention_call": "Retention",
    "resolve_complaint": "Complaint",
    "follow_up_claim": "Claim follow-up",
    "offer_renewal": "Renewal",
    "offer_product": "Product offer",
    "personalized_discount": "Discount",
    "escalate_service": "Escalation",
    "schedule_follow_up": "Follow-up",
    "payment_follow_up": "Payment",
    "no_action": "No action",
}

REVIEW_WORDS = ("special review", "do not match", "does not match", "inconsistent")
OFFER_PHRASES = (
    ("Present refinance options", ("refinance", "interest rate")),
    ("Offer the accident rider they asked about", ("rider",)),
    ("Offer credit life before the loan pays off", ("credit life",)),
    ("Quote a GAP alternative to the dealer policy", ("gap policy",)),
    ("Quote homeowners cover alongside the loan", ("homeowners",)),
    ("Offer the product the customer asked about", ("send a quote", "hear the options")),
)


def money(value: float) -> str:
    return f"${value:,.0f}"


def as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def initials(name: str) -> str:
    parts = [part for part in name.split() if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def tenure_label(months: int) -> str:
    years, rest = divmod(months, 12)
    if years <= 0:
        return f"{rest} months"
    if rest == 0:
        return f"{years} year" if years == 1 else f"{years} years"
    year_word = "year" if years == 1 else "years"
    return f"{years} {year_word} {rest} months"


def _has_phrase(text: str, phrases: tuple[str, ...] | list[str]) -> bool:
    lowered = text.lower()
    return any(contains(lowered, phrase) for phrase in phrases)


def _quote_evidence(interaction: dict | None) -> str | None:
    if not interaction or not interaction.get("quote"):
        return None
    when = as_date(interaction["occurred_on"]).strftime("%b %d")
    channel = interaction["channel"].lower()
    return f"{channel.capitalize()} on {when}: “{interaction['quote']}”"


def build_customer(payload: dict, today: date | None = None) -> dict:
    today = today or date.today()
    customer = payload["customer"]
    products = [_with_days(product, today) for product in payload["products"]]
    payments = sorted(payload["payments"], key=lambda item: item["paid_on"], reverse=True)
    cases = [_with_case_age(case, today) for case in payload["cases"]]
    interactions = sorted(payload["interactions"], key=lambda item: item["occurred_on"], reverse=True)
    actions = sorted(payload["actions"], key=lambda item: item["created_on"], reverse=True)
    facing = [item for item in interactions if item["channel"] != "Note"]
    latest = facing[0] if facing else (interactions[0] if interactions else None)
    previous = facing[1] if len(facing) > 1 else None
    sentiment = latest["sentiment"] if latest else "Neutral"
    previous_sentiment = previous["sentiment"] if previous else None
    trend = f"{previous_sentiment} → {sentiment}" if previous_sentiment and previous_sentiment != sentiment else None

    recent_payments = [item for item in payments if (today - as_date(item["paid_on"])).days <= 120]
    missed = [item for item in recent_payments if item["status"] == "Missed"]
    lates = [item for item in recent_payments if item["status"] == "Late"]
    loan_numbers = {product["number"] for product in products if product["kind"] == "Loan"}
    loan_misses = [item for item in missed if item["product_number"] in loan_numbers]
    lapsed = [product for product in products if product["status"] == "Lapsed"]
    open_cases = [case for case in cases if case["status"] in OPEN]
    open_complaints = [case for case in open_cases if case["kind"] == "Complaint"]
    open_claims = [case for case in open_cases if case["kind"] == "Claim"]
    open_services = [case for case in open_cases if case["kind"] == "Service"]
    denied_claims = [case for case in cases if case["kind"] == "Claim" and case["status"] == "Denied"]
    aged_claims = [case for case in open_claims if case["age_days"] >= 14]
    renewal_options = [
        product
        for product in products
        if product["kind"] == "Policy"
        and product["status"] != "Lapsed"
        and product["renewal_in_days"] is not None
        and product["renewal_in_days"] >= 0
    ]
    nearest = min(renewal_options, key=lambda product: product["renewal_in_days"]) if renewal_options else None
    body_text = "\n".join(item["body"] for item in interactions)
    regulator = _has_phrase(body_text, REGULATOR_PHRASES)
    churn_language = _has_phrase(body_text, CHURN_PHRASES) or any(item["churn_signals"] for item in interactions)
    special_cases = [case for case in open_claims if _has_phrase(f"{case['title']} {case['description']}", REVIEW_WORDS)]
    covenant = [case for case in open_services if "covenant" in f"{case['title']} {case['description']}".lower()]
    high_value = customer["customer_value"] >= HIGH_VALUE
    dispute_open = bool(open_complaints or open_claims or denied_claims)

    risk_score, factors = _risk(
        sentiment=sentiment,
        churn_language=churn_language,
        open_complaints=open_complaints,
        open_claims=open_claims,
        aged_claims=aged_claims,
        denied_claims=denied_claims,
        missed=missed,
        lates=lates,
        lapsed=lapsed,
        regulator=regulator and dispute_open,
        special_cases=special_cases,
        open_services=open_services,
        covenant=covenant,
        nearest=nearest,
    )
    risk_level = "High" if risk_score >= 55 else "Medium" if risk_score >= 26 else "Low"
    churn = _churn(
        sentiment=sentiment,
        churn_language=churn_language,
        open_complaints=open_complaints,
        aged_claims=aged_claims,
        missed=missed,
        lapsed=lapsed,
        regulator=regulator and dispute_open,
        nearest=nearest,
    )

    decision_ctx = {
        "customer": customer,
        "products": products,
        "sentiment": sentiment,
        "latest": latest,
        "high_value": high_value,
        "regulator": regulator,
        "dispute_open": dispute_open,
        "special_cases": special_cases,
        "loan_misses": loan_misses,
        "missed": missed,
        "open_complaints": open_complaints,
        "open_claims": open_claims,
        "open_services": open_services,
        "denied_claims": denied_claims,
        "lapsed": lapsed,
        "nearest": nearest,
        "churn_language": churn_language,
        "facing": facing,
        "today": today,
    }
    nba = _decide(**decision_ctx)
    nba = {
        **nba,
        "evidence_links": _link_evidence(nba["evidence"], interactions, cases, payments, products),
        "alternatives": _alternatives(decision_ctx, nba["action_type"]),
        "selection": ENGINE_SELECTION,
        **_confidence(decision_ctx),
    }
    outcome = _latest_result(actions)
    if outcome and outcome.get("result") in RESULT_EFFECT:
        risk_delta, churn_delta, factor = RESULT_EFFECT[outcome["result"]]
        risk_score = min(96, max(0, risk_score + risk_delta))
        churn = min(0.94, max(0.04, round(churn + churn_delta, 2)))
        risk_level = "High" if risk_score >= 55 else "Medium" if risk_score >= 26 else "Low"
        factors = [*factors, factor]

    concerns = _unique(item for interaction in facing for item in interaction["concerns"])
    topics = _unique(item for interaction in facing for item in interaction["topics"])
    churn_indicators = _unique(item for interaction in interactions for item in interaction["churn_signals"])
    if lapsed:
        churn_indicators.append("A policy on the file has lapsed")
    if missed:
        churn_indicators.append(f"{len(missed)} missed payment(s) in the last 120 days")
    if regulator and dispute_open:
        churn_indicators.append("Regulator or insurance department was mentioned")
    facts = _facts(products, open_cases, denied_claims, missed, payments, latest)
    summary = _summary(customer, sentiment, latest, nearest, open_cases, nba)
    sources = {item["source"] for item in interactions}
    if sources == {"llm"}:
        source = "llm"
    elif "llm" in sources:
        source = "mixed"
    else:
        source = "rules"
    urgencies = [item["urgency"] for item in facing]
    if regulator or len(missed) >= 2 or (latest and latest["urgency"] == "High"):
        urgency = "High"
    elif "Medium" in urgencies or open_cases or missed:
        urgency = "Medium"
    else:
        urgency = latest["urgency"] if latest else "Low"

    story = None
    if customer.get("story_kicker"):
        story = {
            "kicker": customer["story_kicker"],
            "title": customer["story_title"],
            "blurb": customer["story_blurb"],
        }

    return {
        "customer": {
            "id": customer["id"],
            "name": customer["name"],
            "initials": initials(customer["name"]),
            "age": customer["age"],
            "city": customer["city"],
            "region": customer["region"],
            "occupation": customer["occupation"],
            "email": customer["email"],
            "phone": customer["phone"],
            "segment": customer["segment"],
            "book": customer["book"],
            "tenure_months": customer["tenure_months"],
            "tenure_label": tenure_label(customer["tenure_months"]),
            "customer_value": customer["customer_value"],
            "joined_on": customer["joined_on"],
            "high_value": high_value,
        },
        "risk": {
            "level": risk_level,
            "score": risk_score,
            "churn_probability": round(churn, 2),
            "factors": factors,
        },
        "insights": {
            "sentiment": sentiment,
            "previous_sentiment": previous_sentiment,
            "trend": trend,
            "intent": latest["intent"] if latest else "No recent conversation",
            "concerns": concerns[:6],
            "topics": topics[:8],
            "urgency": urgency,
            "facts": facts[:7],
            "churn_indicators": churn_indicators[:6],
            "summary": summary,
            "source": source,
        },
        "nba": nba,
        "products": products,
        "payments": payments,
        "cases": cases,
        "timeline": _timeline(customer, interactions, cases, actions, products, payments),
        "actions": [_public_action(action) for action in actions],
        "sources": _sources(products, payments, cases, interactions, actions),
        "story": story,
        "open_issues": len(open_cases),
        "next_renewal_days": nearest["renewal_in_days"] if nearest else None,
        "headline_product": (nearest or products[0])["name"] if products else "No product",
    }


def summarize_row(full: dict) -> dict:
    customer = full["customer"]
    return {
        "id": customer["id"],
        "name": customer["name"],
        "initials": customer["initials"],
        "city": customer["city"],
        "region": customer["region"],
        "occupation": customer["occupation"],
        "segment": customer["segment"],
        "book": customer["book"],
        "tenure_months": customer["tenure_months"],
        "customer_value": customer["customer_value"],
        "high_value": customer["high_value"],
        "risk_level": full["risk"]["level"],
        "risk_score": full["risk"]["score"],
        "churn_probability": full["risk"]["churn_probability"],
        "sentiment": full["insights"]["sentiment"],
        "intent": full["insights"]["intent"],
        "nba": {
            "action_type": full["nba"]["action_type"],
            "title": full["nba"]["title"],
            "priority": full["nba"]["priority"],
            "reason": full["nba"]["reason"],
            "evidence_preview": full["nba"]["evidence"][0] if full["nba"]["evidence"] else "",
        },
        "open_issues": full["open_issues"],
        "next_renewal_days": full["next_renewal_days"],
        "headline_product": full["headline_product"],
        "story": full["story"],
    }


def _with_days(product: dict, today: date) -> dict:
    renewal_in_days = None
    if product.get("renewal_on"):
        renewal_in_days = (as_date(product["renewal_on"]) - today).days
    status = product["status"]
    if status == "Lapsed":
        health = "Lapsed"
    elif status == "Delinquent":
        health = "Overdue"
    elif product["kind"] == "Policy" and renewal_in_days is not None and 0 <= renewal_in_days <= 30:
        health = "Renewal due"
        if status == "Active":
            status = "Pending Renewal"
    else:
        health = "Current"
    return {**product, "status": status, "health": health, "renewal_in_days": renewal_in_days}


def _with_case_age(case: dict, today: date) -> dict:
    return {**case, "age_days": (today - as_date(case["opened_on"])).days}


def _unique(items) -> list[str]:
    found: list[str] = []
    for item in items:
        if item and item not in found:
            found.append(item)
    return found


def _risk(**kwargs) -> tuple[int, list[str]]:
    score = 0
    factors: list[str] = []
    if kwargs["sentiment"] == "Negative":
        score += 18
        factors.append("Latest customer conversation is negative.")
    if kwargs["churn_language"]:
        score += 16
        factors.append("The customer used language associated with leaving.")
    if kwargs["open_complaints"]:
        score += 22
        factors.append(f"Open complaint: {kwargs['open_complaints'][0]['title']}.")
    if kwargs["aged_claims"]:
        claim = kwargs["aged_claims"][0]
        score += 18
        factors.append(f"{claim['id']} has been open for {claim['age_days']} days.")
    elif kwargs["open_claims"]:
        claim = kwargs["open_claims"][0]
        score += 8
        factors.append(f"{claim['id']} is open ({claim['status'].lower()}).")
    if kwargs["denied_claims"]:
        score += 12
        factors.append(f"Claim {kwargs['denied_claims'][0]['id']} was denied and is still part of the live story.")
    if kwargs["missed"]:
        score += min(40, 20 * len(kwargs["missed"]))
        factors.append(f"{len(kwargs['missed'])} missed payment(s) in the last 120 days.")
        if kwargs["sentiment"] != "Negative":
            score += 10
            factors.append("The delinquency is on file even though the tone is cooperative.")
    elif kwargs["lates"]:
        score += 8
        factors.append("A recent payment was late and has since been cured.")
    if kwargs["lapsed"]:
        score += 30
        factors.append(f"{kwargs['lapsed'][0]['name']} is lapsed.")
    if kwargs["regulator"]:
        score += 14
        factors.append("The customer mentioned a regulator or insurance department.")
    if kwargs["special_cases"]:
        score += 22
        factors.append("A claim file is in special review because the documents do not agree.")
    if kwargs["covenant"]:
        score += 28
        factors.append("A credit covenant review is due.")
    elif kwargs["open_services"]:
        score += 14
        factors.append(f"Open service request: {kwargs['open_services'][0]['title']}.")
    nearest = kwargs["nearest"]
    if nearest and nearest["renewal_in_days"] <= 30 and kwargs["sentiment"] == "Negative":
        score += 10
        factors.append(f"{nearest['name']} renews in {nearest['renewal_in_days']} days while sentiment is negative.")
    if not factors:
        factors.append("No material risk signals in the current file.")
    return min(score, 96), factors


def _churn(**kwargs) -> float:
    churn = 0.08
    if kwargs["sentiment"] == "Negative":
        churn += 0.22
    if kwargs["churn_language"]:
        churn += 0.28
    if kwargs["open_complaints"]:
        churn += 0.12
    if kwargs["aged_claims"]:
        churn += 0.08
    if kwargs["missed"]:
        churn += 0.18
    if kwargs["lapsed"]:
        churn += 0.4
    if kwargs["regulator"]:
        churn += 0.1
    nearest = kwargs["nearest"]
    if nearest and nearest["renewal_in_days"] <= 30 and kwargs["sentiment"] == "Negative":
        churn += 0.1
    return min(churn, 0.94)


def _decide(**ctx) -> dict:
    reasoning: list[str] = []
    customer = ctx["customer"]
    latest = ctx["latest"]
    quote = _quote_evidence(latest)

    if ctx["regulator"] and ctx["dispute_open"]:
        reasoning.append("Escalation rule matched: regulator language is on file and a dispute is still open.")
        complaint = ctx["open_complaints"][0] if ctx["open_complaints"] else None
        denied = ctx["denied_claims"][0] if ctx["denied_claims"] else None
        evidence = []
        if denied:
            evidence.append(f"{denied['id']} was denied — {denied['title']}.")
        if complaint:
            evidence.append(f"{complaint['id']} has been open for {complaint['age_days']} days.")
        if quote:
            evidence.append(quote)
        return _pack(
            "escalate_service",
            "Escalate to a senior resolver today",
            "High",
            f"{customer['name'].split()[0]} has raised a regulator or insurance department while the dispute is still open. This is a service-recovery case, not a sales conversation.",
            "Reduce the chance of a regulatory complaint and keep the dispute from becoming a lapse.",
            "Name a senior owner, apologize for the unexplained decision, and commit to a written update within one business day. Do not open a product conversation.",
            evidence,
            reasoning,
            "Escalated to a senior resolver. Committed to a written update within one business day.",
        )
    reasoning.append("Escalation rule not matched: no regulator threat on an open dispute.")

    if ctx["special_cases"]:
        case = ctx["special_cases"][0]
        reasoning.append(f"Special-review rule matched: {case['id']} is flagged because the file does not agree with itself.")
        evidence = [f"{case['id']} — {case['title']}. {case['description']}"]
        if quote:
            evidence.append(quote)
        return _pack(
            "escalate_service",
            "Escalate the claim to special review and pause promises",
            "High",
            "The claim file has an internal inconsistency. The next action is a controlled review, not a concession or a payout estimate.",
            "Protect claims accuracy and avoid confirming a settlement the file does not support.",
            "Tell the customer the file is with a specialist and give a status date. Do not estimate a payout.",
            evidence,
            reasoning,
            "Referred the file to special review. Gave the customer a status date and made no payment promise.",
        )
    reasoning.append("Special-review rule not matched.")

    if ctx["loan_misses"]:
        count = len(ctx["loan_misses"])
        amount = sum(item["amount"] for item in ctx["loan_misses"])
        priority = "High" if count >= 2 else "Medium"
        title = "Call now and agree a hardship plan" if count >= 2 else "Call about the missed installment"
        reasoning.append(f"Delinquency rule matched: {count} missed loan payment(s).")
        evidence = [f"{count} missed installment(s) totaling {money(amount)} in the last 120 days."]
        if quote:
            evidence.append(quote)
        reason = (
            f"{customer['name'].split()[0]} is behind on the loan. "
            + ("Two payments are missed, so this should be a hardship conversation before it rolls to collections." if count >= 2 else "One installment is missed and the tone is still workable, so agree an amount and a date.")
        )
        return _pack(
            "payment_follow_up",
            title,
            priority,
            reason,
            "Collect a workable payment and keep the account from moving toward charge-off.",
            "Confirm what they can pay and the date. Document the arrangement. Waive a fee only inside policy.",
            evidence,
            reasoning,
            "Agreed a payment amount and date. Documented the arrangement on the loan.",
        )
    if ctx["missed"]:
        reasoning.append("Loan delinquency rule not matched. Missed premium payments are considered later if the policy is not already lapsed.")
    else:
        reasoning.append("Delinquency rule not matched: no missed payments in the last 120 days.")

    if ctx["open_complaints"]:
        complaint = ctx["open_complaints"][0]
        priority = "High" if ctx["sentiment"] == "Negative" else "Medium"
        reasoning.append(f"Complaint rule matched: {complaint['id']} is {complaint['status'].lower()} and sentiment is {ctx['sentiment'].lower()}.")
        evidence = [f"{complaint['id']} open {complaint['age_days']} days — {complaint['title']}."]
        if ctx["denied_claims"]:
            denied = ctx["denied_claims"][0]
            evidence.append(f"Related claim {denied['id']} status is denied.")
        if quote:
            evidence.append(quote)
        return _pack(
            "resolve_complaint",
            "Resolve the open complaint before any offer",
            priority,
            f"{customer['name'].split()[0]} still has an unexplained dispute. A renewal or product conversation will land badly until someone owns {complaint['id']}.",
            "Recover trust and stop the complaint from turning into a lapse or a regulatory file.",
            "Explain the decision in plain language, offer a supervisor review, and agree the next update time on the call.",
            evidence,
            reasoning,
            f"Reviewed {complaint['id']} with the customer and set the next update.",
        )
    reasoning.append("Complaint rule not matched: no open complaint.")

    nearest = ctx["nearest"]
    renewal_squeeze = nearest is not None and nearest["renewal_in_days"] <= 45 and (
        ctx["open_claims"] or (ctx["sentiment"] == "Negative" and (ctx["churn_language"] or ctx["open_services"]))
    )
    if renewal_squeeze and nearest is not None:
        claim_bit = ""
        evidence = [f"{nearest['name']} ({nearest['number']}) renews in {nearest['renewal_in_days']} days."]
        if ctx["open_claims"]:
            claim = ctx["open_claims"][0]
            claim_bit = f" {claim['id']} is still {claim['status'].lower()} after {claim['age_days']} days."
            evidence.append(f"{claim['id']} for {money(claim['amount'] or 0)} — {claim['title']}.")
            title = "Call with a renewal plan and close the open claim first"
            talk = "Start with the claim. Give a decision date in writing. Only then confirm how renewal will work. Do not lead with a cross-sell."
        else:
            title = "Place a retention call before renewal"
            talk = "Acknowledge the dissatisfaction first and ask what would make them stay. Do not open with price."
        if quote:
            evidence.append(quote)
        reasoning.append("Renewal-risk rule matched: a near renewal is colliding with an unresolved issue or clear exit language.")
        if ctx["open_claims"]:
            reasoning.append("A discount was not selected because a claim is still open. Fix the claim path first.")
        return _pack(
            "retention_call",
            title,
            "High",
            f"{customer['name'].split()[0]} is close to renewal and the file is not calm.{claim_bit} Latest sentiment is {ctx['sentiment'].lower()}.",
            "Reduce the chance of a lapse and protect the relationship value on the file.",
            talk,
            evidence,
            reasoning,
            "Called ahead of renewal, acknowledged the open issue, and agreed a written next step.",
        )
    if nearest and nearest["renewal_in_days"] <= 45:
        reasoning.append(
            f"Renewal-risk rule not matched: {nearest['name']} renews in {nearest['renewal_in_days']} days, but there is no open claim or exit language."
        )
    else:
        reasoning.append("Renewal-risk rule not matched: no policy renews inside 45 days with an active problem.")

    if ctx["open_claims"]:
        claim = ctx["open_claims"][0]
        no_rush = bool(latest and "no rush" in latest["body"].lower())
        priority = "Low" if no_rush else "Medium"
        reasoning.append(f"Open-claim rule matched: {claim['id']} is {claim['status'].lower()}.")
        evidence = [f"{claim['id']} opened {claim['age_days']} days ago — {claim['title']}."]
        if claim.get("amount"):
            evidence.append(f"Amount on the file: {money(claim['amount'])}.")
        if quote:
            evidence.append(quote)
        return _pack(
            "follow_up_claim",
            "Follow up on the open claim with a clear status",
            priority,
            f"{claim['id']} is still {claim['status'].lower()}. The customer needs a status and a date, even when the tone is calm.",
            "Shorten the claim cycle and keep a service delay from becoming the reason they leave later.",
            "Give the current status, name the next document or decision, and promise a date you can keep.",
            evidence,
            reasoning,
            f"Updated the customer on {claim['id']} and recorded the next decision date.",
        )
    reasoning.append("Open-claim rule not matched.")

    if ctx["lapsed"]:
        policy = ctx["lapsed"][0]
        reasoning.append(f"Win-back rule matched: {policy['name']} is lapsed.")
        evidence = [f"{policy['name']} ({policy['number']}) status is lapsed."]
        if ctx["missed"]:
            evidence.append(f"{len(ctx['missed'])} recent premium payment(s) were missed before the lapse.")
        if quote:
            evidence.append(quote)
        return _pack(
            "retention_call",
            "Win-back call on the lapsed policy",
            "High",
            f"{policy['name']} has already lapsed. A standard renewal reminder is too late; this is a win-back conversation about price and the reason they left.",
            "Recover a lapsed policy if the number can be matched, and learn whether the rest of the book is at risk.",
            "Ask why they left, confirm the competing number, and offer a match only inside authority. Do not pretend the policy is still in force.",
            evidence,
            reasoning,
            "Win-back call completed. Recorded the competing price and whether a match was offered.",
        )

    if ctx["open_services"]:
        service = ctx["open_services"][0]
        evidence = [f"{service['id']} open {service['age_days']} days — {service['title']}."]
        if quote:
            evidence.append(quote)
        if ctx["high_value"] and ctx["sentiment"] == "Negative":
            reasoning.append("Service-recovery rule matched: a high-value customer is negative about an open service request.")
            reasoning.append("A discount was not selected. The failure is service, not price.")
            return _pack(
                "retention_call",
                "Senior retention call to fix the service failure",
                "High",
                f"{customer['name'].split()[0]} is a {customer['segment'].lower()} client, and “{service['title']}” is still open. Lead with the missed promise, not a concession.",
                "Protect a high-value relationship by finishing the service request before it becomes a move-away.",
                "Complete the outstanding change on the call if the authority is there. Apologize once, specifically. Do not offer a discount.",
                evidence,
                reasoning,
                f"Senior callback completed. {service['id']} updated and the customer told what changed.",
            )
        priority = "High" if ctx["sentiment"] == "Negative" else "Medium"
        reasoning.append(f"Service-request rule matched: {service['id']} is still open.")
        return _pack(
            "schedule_follow_up",
            "Call back and finish the open service request",
            priority,
            f"{service['title']} is still open after {service['age_days']} days. Close the loop before it turns into a complaint.",
            "Keep a routine service miss from becoming a complaint or a lost renewal.",
            "Call with the finished item, or with a same-day owner if it is not finished. Do not send another holding email.",
            evidence,
            reasoning,
            f"Followed up on {service['id']} and recorded what was delivered.",
        )
    reasoning.append("Service-request rule not matched.")

    offer = _offer_title(ctx["facing"], ctx["today"])
    if (
        ctx["high_value"]
        and ctx["sentiment"] == "Negative"
        and ctx["churn_language"]
        and not ctx["open_claims"]
        and not ctx["open_complaints"]
        and not ctx["open_services"]
        and not ctx["missed"]
    ):
        reasoning.append("Concession rule matched: high value, exit language, and no open service failure to fix first.")
        evidence = [f"Relationship value {money(customer['customer_value'])}."]
        if nearest:
            evidence.append(f"{nearest['name']} renews in {nearest['renewal_in_days']} days.")
        if quote:
            evidence.append(quote)
        return _pack(
            "personalized_discount",
            "Offer a bounded renewal concession",
            "High",
            f"{customer['name'].split()[0]} is shopping and said the price is the issue. There is no open claim or complaint to fix first, so a bounded concession is the relevant lever.",
            "A modest renewal credit is cheaper than replacing this relationship.",
            "Ask what number would keep the policy, and stay inside discount authority. Confirm it in writing.",
            evidence,
            reasoning,
            "Discussed a renewal concession inside authority and recorded the customer's number.",
        )

    if ctx["high_value"] and ctx["sentiment"] == "Negative":
        reasoning.append("High-value negative rule matched without a cleaner service or price trigger.")
        evidence = [f"Relationship value {money(customer['customer_value'])}.", f"Latest sentiment is {ctx['sentiment'].lower()}."]
        if quote:
            evidence.append(quote)
        return _pack(
            "retention_call",
            "Retention call from a senior owner",
            "High",
            "A high-value customer is negative and no narrower service, claim, or price rule explained it. Someone senior should find out why.",
            "Find the real objection before the relationship goes quiet.",
            "Ask what changed. Do not pitch. Agree one follow-up with an owner.",
            evidence,
            reasoning,
            "Senior retention call completed. Recorded the objection and the owner of the next step.",
        )

    if nearest and nearest["renewal_in_days"] <= 75 and ctx["sentiment"] != "Negative" and not ctx["open_claims"]:
        reasoning.append(f"Healthy renewal rule matched: {nearest['name']} renews in {nearest['renewal_in_days']} days and sentiment is {ctx['sentiment'].lower()}.")
        priority = "High" if nearest["renewal_in_days"] <= 30 else "Medium"
        evidence = [f"{nearest['name']} ({nearest['number']}) renews in {nearest['renewal_in_days']} days. Current status: {nearest['health']}."]
        if quote:
            evidence.append(quote)
        return _pack(
            "offer_renewal",
            "Send a personalized renewal offer",
            priority,
            f"{nearest['name']} is inside the renewal window and the relationship is calm. Use the conversation to confirm cover, not to save a complaint.",
            "Hold the renewal and update limits where the customer's circumstances changed.",
            "Confirm what changed in the home or the household, then send options with a clear recommendation. Do not discount a healthy renewal by default.",
            evidence,
            reasoning,
            "Renewal options sent. Recorded any change in cover the customer asked for.",
        )

    if offer and ctx["sentiment"] != "Negative" and not ctx["missed"] and not ctx["open_claims"] and not ctx["open_complaints"]:
        reasoning.append(f"Product rule matched from the customer's own words: {offer}.")
        evidence = [offer + "."]
        if quote:
            evidence.append(quote)
        gap = _protection_gap(ctx["products"])
        if gap:
            evidence.append(gap)
        return _pack(
            "offer_product",
            offer,
            "Medium",
            f"{customer['name'].split()[0]} asked about this, and there is no service failure or missed payment that should come first.",
            "Add a product the customer already has a reason to consider, without interrupting a service issue.",
            "Quote only the product they mentioned. Compare it with what they have now. Stop if they are not interested.",
            evidence,
            reasoning,
            "Sent the quote the customer asked for and recorded their response.",
        )

    if _wants_callback(ctx["facing"], ctx["today"]):
        reasoning.append("Callback rule matched: the customer asked for a follow-up and no higher-priority case is open.")
        evidence = []
        if quote:
            evidence.append(quote)
        else:
            evidence.append("A recent conversation asked for a follow-up.")
        return _pack(
            "schedule_follow_up",
            "Schedule the follow-up that was promised",
            "Medium",
            "Someone promised a check-back. Missing it would create a service failure on an otherwise quiet file.",
            "Keep a small promise and avoid a second contact about the same issue.",
            "Call or write on the day that was promised. Confirm the one item they asked about and then stop.",
            evidence,
            reasoning,
            "Completed the promised follow-up.",
        )

    if ctx["missed"]:
        reasoning.append("Premium delinquency remained after the lapse check.")
        evidence = [f"{len(ctx['missed'])} missed premium payment(s) in the last 120 days."]
        return _pack(
            "payment_follow_up",
            "Call about the missed premium",
            "Medium",
            "A premium payment was missed and the policy is still on the books.",
            "Collect the premium before the policy lapses.",
            "Confirm the amount, the date, and whether autopay failed.",
            evidence,
            reasoning,
            "Called about the missed premium and recorded the payment date.",
        )

    reasoning.append("No retention, service, renewal, or offer rule matched.")
    evidence = ["Payments are current."] if not ctx["missed"] else []
    evidence.append("No open claim, complaint, or service request.")
    if ctx["sentiment"] == "Positive" and quote:
        evidence.append(quote)
    elif latest:
        evidence.append(f"Latest {latest['channel'].lower()} sentiment is {ctx['sentiment'].lower()}.")
    return _pack(
        "no_action",
        "No action required",
        "None",
        "Payments are current, nothing material is open, and recent sentiment does not call for a save or an offer. A courtesy pitch would add noise.",
        "Preserve goodwill and spend outreach time on the files that are actually moving.",
        "Do not contact unless they call in.",
        evidence,
        reasoning,
        "Reviewed the file. No outreach logged.",
    )


def _pack(action_type, title, priority, reason, impact, talk, evidence, reasoning, note) -> dict:
    reasoning = [*reasoning, f"Decision: {title}."]
    return {
        "action_type": action_type,
        "title": title,
        "priority": priority,
        "reason": reason,
        "expected_impact": impact,
        "talk_track": talk,
        "evidence": [item for item in evidence if item][:5],
        "reasoning": reasoning,
        "suggested_note": note,
    }


def _offer_title(facing: list[dict], today: date) -> str | None:
    for interaction in facing:
        if (today - as_date(interaction["occurred_on"])).days > 150:
            continue
        lowered = interaction["body"].lower()
        for title, phrases in OFFER_PHRASES:
            if any(contains(lowered, phrase) for phrase in phrases):
                return title
    return None


def _wants_callback(facing: list[dict], today: date) -> bool:
    phrases = ["check back", "call me tomorrow", "please call me", "call me today", "call me back"]
    for interaction in facing:
        if (today - as_date(interaction["occurred_on"])).days > 150:
            continue
        if _has_phrase(interaction["body"], phrases):
            return True
    return False


def _protection_gap(products: list[dict]) -> str | None:
    loans = [product for product in products if product["kind"] == "Loan" and product["status"] != "Lapsed"]
    policies = [product for product in products if product["kind"] == "Policy" and product["status"] not in {"Lapsed"}]
    if loans and not policies:
        return f"{loans[0]['name']} is on the books with no Northline protection policy."
    return None


def _facts(products, open_cases, denied_claims, missed, payments, latest) -> list[str]:
    facts = []
    for product in products:
        if product["kind"] == "Loan":
            line = f"{product['name']} ({product['number']}) outstanding {money(product['outstanding'])}, installment {money(product['installment'])} {product['frequency'].lower()}."
        else:
            renewal = ""
            if product["renewal_in_days"] is not None and product["status"] != "Lapsed":
                renewal = f" Renews in {product['renewal_in_days']} days."
            elif product["status"] == "Lapsed":
                renewal = " Status: lapsed."
            line = f"{product['name']} ({product['number']}) premium {money(product['installment'])} {product['frequency'].lower()}.{renewal}"
        facts.append(line)
    for case in open_cases:
        amount = f" Amount {money(case['amount'])}." if case.get("amount") else ""
        facts.append(f"{case['kind']} {case['id']} is {case['status'].lower()} ({case['age_days']} days).{amount}")
    for case in denied_claims[:1]:
        facts.append(f"{case['id']} was denied: {case['title']}.")
    if missed:
        facts.append(f"{len(missed)} missed payment(s) in the last 120 days.")
    elif payments:
        last = payments[0]
        facts.append(f"Last payment {last['status'].lower()} on {as_date(last['paid_on']).strftime('%b %d')} for {money(last['amount'])}.")
    if latest and latest.get("quote"):
        facts.append(f"Latest {latest['channel'].lower()}: “{latest['quote']}”")
    return facts


def _summary(customer, sentiment, latest, nearest, open_cases, nba) -> str:
    first = customer["name"].split()[0]
    book = {"Insurance": "insurance", "Lending": "lending", "Both": "insurance and lending"}.get(customer["book"], customer["book"].lower())
    segment = "SME" if customer["segment"] == "SME" else customer["segment"].lower()
    article = "an" if segment[:1].lower() in "aeiou" else "a"
    parts = [
        f"{customer['name']} is {article} {segment} {book} customer in {customer['city']}, on the book for {tenure_label(customer['tenure_months'])}, with a relationship value of {money(customer['customer_value'])}."
    ]
    if latest and latest.get("quote") and sentiment == "Negative":
        parts.append(f"The latest {latest['channel'].lower()} is negative: “{latest['quote']}”")
    elif latest:
        parts.append(f"The latest {latest['channel'].lower()} sentiment is {sentiment.lower()}, with intent recorded as {latest['intent'].lower()}.")
    if open_cases:
        case = open_cases[0]
        parts.append(f"{case['kind']} {case['id']} ({case['title']}) is {case['status'].lower()}.")
    if nearest:
        parts.append(f"{nearest['name']} renews in {nearest['renewal_in_days']} days.")
    parts.append(f"Next best action: {nba['title'][0].lower() + nba['title'][1:]}.")
    return " ".join(parts)


def _timeline(customer, interactions, cases, actions, products, payments) -> list[dict]:
    events = []
    for item in interactions:
        actor = item["agent"] if item["channel"] == "Note" or item["direction"] in {"Outbound", "Internal"} else customer["name"]
        events.append(
            {
                "id": f"int-{item['id']}",
                "kind": item["channel"],
                "occurred_on": item["occurred_on"],
                "title": item["subject"],
                "detail": item["body"],
                "actor": actor,
                "direction": item["direction"],
                "duration_min": item["duration_min"],
                "sentiment": item["sentiment"],
                "intent": item["intent"],
                "topics": item["topics"],
                "concerns": item["concerns"],
                "urgency": item["urgency"],
                "entities": item["entities"],
                "churn_signals": item["churn_signals"],
                "summary": item["summary"],
                "quote": item["quote"],
                "source": item["source"],
                "ai": True,
                "expandable": True,
            }
        )
    for case in cases:
        events.append(
            {
                "id": f"case-open-{case['id']}",
                "kind": case["kind"],
                "occurred_on": f"{case['opened_on']}T09:00:00",
                "title": f"{case['kind']} opened · {case['title']}",
                "detail": case["description"],
                "actor": "Case file",
                "direction": "Internal",
                "duration_min": None,
                "sentiment": None,
                "intent": None,
                "topics": [],
                "concerns": [],
                "urgency": None,
                "entities": [case["id"]],
                "churn_signals": [],
                "summary": "",
                "quote": "",
                "source": None,
                "ai": False,
                "expandable": True,
            }
        )
        if case.get("closed_on"):
            label = "denied" if case["status"] == "Denied" else "closed"
            events.append(
                {
                    "id": f"case-close-{case['id']}",
                    "kind": case["kind"],
                    "occurred_on": f"{case['closed_on']}T16:00:00",
                    "title": f"{case['kind']} {label} · {case['title']}",
                    "detail": case["description"],
                    "actor": "Case file",
                    "direction": "Internal",
                    "duration_min": None,
                    "sentiment": None,
                    "intent": None,
                    "topics": [],
                    "concerns": [],
                    "urgency": None,
                    "entities": [case["id"]],
                    "churn_signals": [],
                    "summary": "",
                    "quote": "",
                    "source": None,
                    "ai": False,
                    "expandable": True,
                }
            )
    for product in products:
        stamp = product.get("started_on") or product.get("renewal_on")
        if not stamp:
            continue
        renewal = ""
        if product.get("renewal_in_days") is not None and product["status"] != "Lapsed":
            renewal = f" Renews in {product['renewal_in_days']} days."
        events.append(
            {
                "id": f"product-{product['id']}",
                "kind": "Policy" if product["kind"] == "Policy" else "Loan",
                "occurred_on": f"{as_date(stamp).isoformat()}T08:00",
                "title": f"{product['name']} · {product['number']}",
                "detail": f"{product['status']}.{renewal} {('Premium' if product['kind'] == 'Policy' else 'Installment')} {money(product['installment'])} {product['frequency'].lower()}.",
                "actor": "Product file",
                "direction": "Internal",
                "duration_min": None,
                "sentiment": None,
                "intent": None,
                "topics": [],
                "concerns": [],
                "urgency": None,
                "entities": [product["number"]],
                "churn_signals": [],
                "summary": "",
                "quote": "",
                "source": None,
                "ai": False,
                "expandable": True,
            }
        )
    seen_payments = set()
    latest_payment = payments[0]["id"] if payments else None
    for payment in payments:
        if payment["status"] not in {"Missed", "Late"} and payment["id"] != latest_payment:
            continue
        if payment["id"] in seen_payments:
            continue
        seen_payments.add(payment["id"])
        events.append(
            {
                "id": f"pay-{payment['id']}",
                "kind": "Payment",
                "occurred_on": f"{as_date(payment['paid_on']).isoformat()}T12:00",
                "title": f"{payment['status']} payment · {payment['product_name']}",
                "detail": f"{money(payment['amount'])} on {payment['product_number']}. Status: {payment['status']}.",
                "actor": "Payment file",
                "direction": "Internal",
                "duration_min": None,
                "sentiment": None,
                "intent": None,
                "topics": [],
                "concerns": [],
                "urgency": None,
                "entities": [payment["product_number"]],
                "churn_signals": [],
                "summary": "",
                "quote": "",
                "source": None,
                "ai": False,
                "expandable": True,
            }
        )
    for action in actions:
        lines = []
        if action.get("owner"):
            lines.append(f"Owner: {action['owner']}")
        if action.get("priority"):
            lines.append(f"Priority: {action['priority']}")
        if action.get("due_on"):
            lines.append(f"Due: {action['due_on']}")
        if action.get("result"):
            lines.append(f"Outcome: {action['result']}")
        if action.get("risk_before") and action.get("risk_after"):
            lines.append(f"Risk: {action['risk_before']} → {action['risk_after']}")
        if action.get("nba_before") and action.get("nba_after") and action["nba_before"] != action["nba_after"]:
            lines.append(f"Recommendation: {action['nba_before']} → {action['nba_after']}")
        if action.get("note"):
            lines.append(action["note"])
        events.append(
            {
                "id": f"action-{action['id']}",
                "kind": "Action",
                "occurred_on": action["created_on"],
                "title": f"{action['outcome']}: {action['title']}",
                "detail": "\n".join(lines),
                "actor": action.get("owner") or "Relationship manager",
                "direction": "Internal",
                "duration_min": None,
                "sentiment": None,
                "intent": None,
                "topics": [],
                "concerns": [],
                "urgency": None,
                "entities": [],
                "churn_signals": [],
                "summary": "",
                "quote": "",
                "source": None,
                "ai": False,
                "expandable": True,
            }
        )
    events.sort(key=lambda item: str(item["occurred_on"]), reverse=True)
    return events


def _public_action(action: dict) -> dict:
    return {
        "id": action["id"],
        "action_type": action["action_type"],
        "title": action["title"],
        "outcome": action["outcome"],
        "note": action.get("note") or "",
        "owner": action.get("owner") or "",
        "due_on": action.get("due_on"),
        "priority": action.get("priority") or "",
        "result": action.get("result") or "",
        "risk_before": action.get("risk_before") or "",
        "risk_after": action.get("risk_after") or "",
        "nba_before": action.get("nba_before") or "",
        "nba_after": action.get("nba_after") or "",
        "created_on": action["created_on"],
    }


def _latest_result(actions: list[dict]) -> dict | None:
    for action in actions:
        if action.get("result"):
            return action
    return None


def _link_evidence(evidence: list[str], interactions, cases, payments, products) -> list[dict]:
    missed = [item for item in payments if item["status"] == "Missed"]
    latest_payment = payments[0] if payments else None
    links = []
    for text in evidence:
        timeline_id = None
        lowered = text.lower()
        for item in interactions:
            quote = (item.get("quote") or "").strip()
            if len(quote) >= 12 and quote in text:
                timeline_id = f"int-{item['id']}"
                break
        if timeline_id is None:
            for case in cases:
                if case["id"] and case["id"] in text:
                    denied = "denied" in lowered and case.get("closed_on")
                    timeline_id = f"case-close-{case['id']}" if denied else f"case-open-{case['id']}"
                    break
        if timeline_id is None and any(word in lowered for word in ("missed", "installment", "payment", "premium", "delinquen")):
            target = missed[0] if missed else latest_payment
            if target:
                timeline_id = f"pay-{target['id']}"
        if timeline_id is None:
            for product in products:
                if product["number"] in text or product["name"] in text:
                    timeline_id = f"product-{product['id']}"
                    break
        if timeline_id is None:
            facing = [item for item in interactions if item.get("channel") != "Note"]
            target = facing[0] if facing else (interactions[0] if interactions else None)
            if target:
                timeline_id = f"int-{target['id']}"
        links.append({"text": text, "timeline_id": timeline_id})
    return links


def _confidence(ctx: dict) -> dict:
    signals: list[str] = []
    sources: set[str] = set()
    latest = ctx.get("latest")
    if latest:
        signals.append("latest interaction")
        channel = latest.get("channel")
        sources.add("Emails" if channel == "Email" else "Calls")
    if ctx.get("sentiment") == "Negative":
        signals.append("negative sentiment")
    elif ctx.get("sentiment") == "Positive":
        signals.append("positive sentiment")
    if any(item.get("churn_signals") for item in ctx.get("facing") or []):
        signals.append("churn language")
    if ctx.get("open_claims") or ctx.get("denied_claims") or ctx.get("special_cases"):
        signals.append("claim file")
        sources.add("Claims")
    if ctx.get("open_complaints"):
        signals.append("open complaint")
        sources.add("Service records")
    if ctx.get("open_services"):
        signals.append("open service request")
        sources.add("Service records")
    if ctx.get("loan_misses") or ctx.get("missed"):
        signals.append("missed payments")
        sources.add("Payments")
    if ctx.get("lapsed"):
        signals.append("lapsed cover")
        sources.add("Policies")
    if ctx.get("nearest"):
        signals.append("renewal date")
        sources.add("Policies")
    loans_matter = ctx.get("loan_misses") or _offer_title(ctx.get("facing") or [], ctx["today"])
    if loans_matter and any(product["kind"] == "Loan" for product in ctx.get("products") or []):
        signals.append("lending relationship")
        sources.add("Loans")
    if ctx.get("high_value"):
        signals.append("relationship value")
    if ctx.get("regulator") and ctx.get("dispute_open"):
        signals.append("regulator language")
    if not signals:
        signals.append("current file")
    if not sources:
        sources.add("Policies")
    score = 58 + len(signals) * 6 + len(sources) * 2
    score = max(64, min(96, score))
    signal_word = "signal" if len(signals) == 1 else "signals"
    source_word = "data source" if len(sources) == 1 else "data sources"
    return {
        "confidence": score,
        "confidence_note": f"Based on {len(signals)} {signal_word} from {len(sources)} {source_word}",
    }


ALT_TITLES = {
    "retention_call": "Retention call",
    "resolve_complaint": "Resolve complaint",
    "follow_up_claim": "Claim follow-up",
    "offer_renewal": "Renewal offer",
    "offer_product": "Product offer",
    "personalized_discount": "Personalized discount",
    "escalate_service": "Escalation",
    "schedule_follow_up": "Scheduled follow-up",
    "payment_follow_up": "Payment follow-up",
    "no_action": "No action",
}


def _add_alternative(options: list[dict], chosen: str, action_type: str, reason: str) -> None:
    if action_type == chosen or any(item["action_type"] == action_type for item in options):
        return
    options.append({"action_type": action_type, "title": ALT_TITLES.get(action_type, action_type), "reason": reason})


def _alternatives(ctx: dict, chosen: str) -> list[dict]:
    options: list[dict] = []
    nearest = ctx.get("nearest")
    open_claim = bool(ctx.get("open_claims"))
    open_complaint = bool(ctx.get("open_complaints"))
    open_service = bool(ctx.get("open_services"))
    first = ctx["customer"]["name"].split()[0]

    if open_claim or open_complaint or (open_service and ctx.get("sentiment") == "Negative"):
        _add_alternative(options, chosen, "personalized_discount", "Discount skipped — an active claim, complaint, or service failure is still unresolved.")
    if chosen == "retention_call" and open_claim:
        _add_alternative(options, chosen, "follow_up_claim", "Claim follow-up alone was set aside — renewal is close, so the call has to cover both.")
    if open_complaint and chosen != "resolve_complaint":
        _add_alternative(options, chosen, "offer_renewal", "Renewal offer skipped — the open complaint has to be closed first.")
    if ctx.get("regulator") and ctx.get("dispute_open") and chosen != "escalate_service":
        _add_alternative(options, chosen, "retention_call", "A standard retention call was set aside — regulator language means this file is escalated.")
    if ctx.get("special_cases"):
        _add_alternative(options, chosen, "follow_up_claim", "A routine claim update was set aside — the file disagrees with itself, so no payout is promised.")
    if ctx.get("loan_misses"):
        _add_alternative(options, chosen, "offer_product", "A product offer was set aside — missed loan payments come first.")
    if ctx.get("lapsed"):
        _add_alternative(options, chosen, "payment_follow_up", "A collections call was set aside — the policy has already lapsed, so this is a win-back.")
    if nearest and nearest["renewal_in_days"] > 75 and chosen != "offer_renewal":
        _add_alternative(options, chosen, "offer_renewal", f"Renewal offer skipped — {nearest['name']} renews in {nearest['renewal_in_days']} days, outside the outreach window.")
    if _offer_title(ctx.get("facing") or [], ctx["today"]) and chosen != "offer_product":
        _add_alternative(options, chosen, "offer_product", f"The product {first} asked about waits until the higher-priority issue is handled.")
    if chosen == "no_action":
        _add_alternative(options, chosen, "retention_call", "A retention call was set aside — sentiment is calm and nothing material is open.")
        _add_alternative(options, chosen, "offer_product", "A product offer was set aside — the customer did not ask, and the file does not show a gap that should interrupt them.")
        if not (nearest and nearest["renewal_in_days"] > 75):
            _add_alternative(options, chosen, "schedule_follow_up", "A follow-up was set aside — nobody asked for a callback.")
    elif chosen != "no_action":
        _add_alternative(options, chosen, "no_action", "Leaving the file alone was set aside — there is a concrete next step with a business reason.")

    fillers = [
        ("schedule_follow_up", "A generic follow-up was set aside — a more specific action matches this file."),
        ("offer_renewal", "A plain renewal offer was not the highest-priority action on this file."),
        ("payment_follow_up", "A payment call was set aside — delinquency is not the leading signal."),
    ]
    for action_type, reason in fillers:
        if len(options) >= 2:
            break
        _add_alternative(options, chosen, action_type, reason)
    return options[:3]


def _sources(products, payments, cases, interactions, actions) -> dict:
    def count(channel: str) -> int:
        return sum(1 for item in interactions if item["channel"] == channel)

    items = [
        {"name": "Policies", "count": sum(1 for product in products if product["kind"] == "Policy")},
        {"name": "Loans", "count": sum(1 for product in products if product["kind"] == "Loan")},
        {"name": "Claims", "count": sum(1 for case in cases if case["kind"] == "Claim")},
        {"name": "Payments", "count": len(payments)},
        {"name": "Calls", "count": count("Call")},
        {"name": "Emails", "count": count("Email")},
        {"name": "Service records", "count": sum(1 for case in cases if case["kind"] in {"Service", "Complaint"})},
    ]
    chats = count("Chat")
    if chats:
        items.append({"name": "Chats", "count": chats})
    stamps = [str(item["occurred_on"]) for item in interactions]
    stamps.extend(str(item["paid_on"]) for item in payments)
    stamps.extend(str(case["opened_on"]) for case in cases)
    stamps.extend(str(case["closed_on"]) for case in cases if case.get("closed_on"))
    stamps.extend(str(action["created_on"]) for action in actions)
    last_updated = max(stamps) if stamps else datetime.now().replace(microsecond=0).isoformat(timespec="minutes")
    analyzed = sum(1 for item in interactions if item["channel"] != "Note")
    return {"items": items, "last_updated": last_updated, "analyzed_interactions": analyzed}
