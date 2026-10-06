from __future__ import annotations

import re

NEG_PHRASES = [
    "not happy",
    "unhappy",
    "frustrated",
    "frustrating",
    "frustration",
    "angry",
    "disappointed",
    "disappointing",
    "terrible",
    "unacceptable",
    "ridiculous",
    "upset",
    "poor service",
    "rude",
    "stressed",
    "worried",
    "worst",
    "still waiting",
    "no one called",
    "hasn't called",
    "has not called",
]

POS_PHRASES = [
    "thank",
    "thanks",
    "grateful",
    "appreciate",
    "happy with",
    "pleased",
    "excellent",
    "smooth",
    "helpful",
    "quickly",
    "quick",
    "great",
    "no complaints",
    "on track",
    "fair with me",
]

CHURN_PHRASES = [
    "switching",
    "another insurer",
    "another lender",
    "cancel my",
    "not renew",
    "won't renew",
    "will not renew",
    "shopping around",
    "state insurance",
    "department of insurance",
    "close my account",
    "take my business",
    "will not recommend",
]

REGULATOR_PHRASES = [
    "state insurance",
    "department of insurance",
    "ombudsman",
    "insurance department",
    "regulator",
]

SCRUB_PHRASES = [
    "no complaints",
    "i'm not upset",
    "i am not upset",
    "not upset",
    "not angry",
    "don't want a discount",
    "do not want a discount",
    "not disputing",
    "nothing is broken",
    "i'm not trying to hide",
    "not a complaint",
]

INTENT_RULES = [
    ("Cancellation risk", ["switching", "another insurer", "another lender", "cancel my", "not renew", "won't renew", "will not renew", "shopping around", "take my business", "will not recommend"]),
    ("Complaint", ["complaint", "supervisor", "rude", "denied the", "partially denied"]),
    ("Payment hardship", ["missed two", "missed the", "hours were cut", "collections", "late fee", "pay half", "charge off"]),
    ("Claim follow-up", ["claim", "reimbursement", "adjuster", "settlement"]),
    ("Renewal", ["renew", "renewal", "renews"]),
    ("Refinance inquiry", ["refinance", "interest rate", "rate review"]),
    ("Product inquiry", ["send a quote", "hear the options", "open if the price", "rider", "credit life", "gap policy", "homeowners"]),
    ("Onboarding help", ["onboarding", "which documents", "portal"]),
    ("Service request", ["beneficiary", "check back", "certificate of insurance", "accountant", "call me tomorrow", "call me today", "called me back"]),
]

CONCERN_RULES = [
    ("Willing to leave if this is not fixed", ["switching", "another insurer", "not renew", "won't renew", "will not renew", "shopping around", "will not recommend"]),
    ("Claim decision is taking too long", ["still in review", "three weeks", "still waiting", "in review"]),
    ("Denial or exclusion was not explained", ["denied the", "exclusion", "supervisor", "reinspection"]),
    ("Payment hardship", ["hours were cut", "missed two", "missed the draft", "collections", "pay half"]),
    ("Service has gone quiet", ["hasn't called", "has not called", "no one called", "third request", "check back", "called me back"]),
    ("Premium feels high versus competitors", ["shopping around", "premium feels high", "premium jumped"]),
    ("Wants a coverage or rate quote", ["send a quote", "hear the options", "rider", "refinance", "homeowners", "credit life", "gap policy"]),
    ("Onboarding is confusing", ["confused", "which documents"]),
    ("Asked for a regulatory escalation", ["state insurance", "department of insurance", "ombudsman"]),
]

TOPIC_RULES = [
    ("Claim", ["claim", "reimbursement", "adjuster"]),
    ("Renewal", ["renew", "renewal", "renews"]),
    ("Complaint", ["complaint", "supervisor", "ombudsman"]),
    ("Billing", ["premium", "payment", "late fee", "autopay", "draft", "emi"]),
    ("Coverage", ["coverage", "rider", "homeowners", "umbrella", "quote"]),
    ("Refinance", ["refinance", "interest rate"]),
    ("Service", ["beneficiary", "certificate", "portal", "advisor", "callback"]),
    ("Retention", ["switching", "shopping around", "not renew"]),
]

URGENCY_HIGH = [
    "urgent",
    "as soon as",
    "third request",
    "collections",
    "unacceptable",
    "call me today",
    *CHURN_PHRASES,
]

URGENCY_MED = ["claim", "renew", "renewal", "renews", "complaint", "missed", "tomorrow", "next week", "refinance"]


def contains(text: str, phrase: str) -> bool:
    return re.search(r"\b" + re.escape(phrase) + r"\b", text) is not None


def _scrub(lowered: str) -> str:
    scrubbed = lowered
    for phrase in SCRUB_PHRASES:
        scrubbed = re.sub(r"\b" + re.escape(phrase) + r"\b", " ", scrubbed)
    return scrubbed


def _count(text: str, phrases: list[str]) -> int:
    return sum(1 for phrase in phrases if contains(text, phrase))


def sentiment_of(lowered: str, scrubbed: str) -> str:
    positive = _count(lowered, POS_PHRASES)
    negative = _count(scrubbed, NEG_PHRASES)
    if negative >= positive + 1:
        return "Negative"
    if positive >= negative + 1:
        return "Positive"
    return "Neutral"


def _best_intent(scrubbed: str) -> str:
    if any(contains(scrubbed, phrase) for phrase in REGULATOR_PHRASES):
        return "Regulatory escalation"
    best_name = "General service"
    best_score = 0
    best_index = 99
    for index, (name, phrases) in enumerate(INTENT_RULES):
        score = _count(scrubbed, phrases)
        if score > best_score or (score == best_score and score > 0 and index < best_index):
            best_name = name
            best_score = score
            best_index = index
    return best_name


def _matched(scrubbed: str, rules: list[tuple[str, list[str]]]) -> list[str]:
    found = []
    for label, phrases in rules:
        if any(contains(scrubbed, phrase) for phrase in phrases):
            found.append(label)
    return found


def _override_intent(intent: str, sentiment: str, scrubbed: str, lowered: str) -> str:
    if intent == "Regulatory escalation":
        return intent
    productish = any(
        contains(scrubbed, phrase)
        for phrase in ["send a quote", "hear the options", "rider", "credit life", "gap policy", "homeowners", "refinance"]
    )
    churnish = any(contains(scrubbed, phrase) for phrase in CHURN_PHRASES)
    grateful = any(contains(lowered, phrase) for phrase in ["thank", "thanks", "grateful", "pleased", "excellent", "happy with"])
    if sentiment == "Positive" and not churnish and not productish and grateful:
        if any(contains(scrubbed, phrase) for phrase in ["renew", "renewal", "renews"]):
            return "Renewal"
        return "Appreciation"
    return intent


def _urgency(lowered: str, scrubbed: str, sentiment: str) -> str:
    churnish = any(contains(scrubbed, phrase) for phrase in CHURN_PHRASES)
    if contains(lowered, "no rush") and not any(contains(scrubbed, phrase) for phrase in URGENCY_HIGH):
        return "Low"
    if churnish or any(contains(scrubbed, phrase) for phrase in URGENCY_HIGH):
        return "High"
    if sentiment == "Positive" and not churnish:
        if any(contains(scrubbed, phrase) for phrase in ["check back", "tomorrow", "next week", "renew", "renewal", "renews"]):
            return "Medium"
        return "Low"
    if sentiment == "Negative" or any(contains(scrubbed, phrase) for phrase in URGENCY_MED):
        return "Medium"
    return "Low"


def _entities(text: str, catalog: list[str]) -> list[str]:
    found: list[str] = []
    for pattern in (r"\$\d[\d,]*(?:\.\d+)?", r"\b(?:POL|LN|CLM|CMP|SRV)-\d+\b"):
        for match in re.findall(pattern, text):
            if match not in found:
                found.append(match)
    lowered = text.lower()
    for item in catalog:
        if item and item.lower() in lowered and item not in found:
            found.append(item)
    return found[:12]


def best_sentence(text: str, needles: list[str]) -> str:
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]
    if not parts:
        return ""

    def score(sentence: str) -> int:
        lowered = sentence.lower()
        return sum(1 for needle in needles if needle and contains(lowered, needle))

    best = max(parts, key=score)
    if score(best) == 0:
        best = max(parts, key=len)
    return best[:280]


def _pretty_churn(scrubbed: str) -> list[str]:
    labels = {
        "switching": "Said they are switching insurers",
        "another insurer": "Mentioned another insurer",
        "another lender": "Mentioned another lender",
        "cancel my": "Talked about cancelling",
        "not renew": "May not renew",
        "won't renew": "May not renew",
        "will not renew": "May not renew",
        "shopping around": "Shopping competitor quotes",
        "state insurance": "Raised the state insurance department",
        "department of insurance": "Raised the insurance department",
        "close my account": "Talked about closing the account",
        "take my business": "Talked about taking the business elsewhere",
        "will not recommend": "Will not recommend the company",
    }
    found = []
    for phrase, label in labels.items():
        if contains(scrubbed, phrase) and label not in found:
            found.append(label)
    return found


def _summary(sentiment: str, intent: str, concerns: list[str], urgency: str) -> str:
    sentence = f"{sentiment} sentiment. Intent: {intent}."
    if concerns:
        sentence += f" {concerns[0]}."
    if urgency == "High":
        sentence += " Urgency is high."
    return sentence


def analyze_text(text: str, catalog: list[str] | None = None) -> dict:
    raw = (text or "").replace("’", "'")
    lowered = raw.lower()
    scrubbed = _scrub(lowered)
    sentiment = sentiment_of(lowered, scrubbed)
    intent = _override_intent(_best_intent(scrubbed), sentiment, scrubbed, lowered)
    concerns = _matched(scrubbed, CONCERN_RULES)
    topics = _matched(scrubbed, TOPIC_RULES)
    churn = _pretty_churn(scrubbed)
    urgency = _urgency(lowered, scrubbed, sentiment)
    needles = [phrase for phrase in CHURN_PHRASES + NEG_PHRASES + ["renewal", "quote", "refinance", "claim", "beneficiary"] if contains(scrubbed, phrase)]
    quote = best_sentence(raw, needles)
    return {
        "sentiment": sentiment,
        "intent": intent,
        "topics": topics,
        "concerns": concerns,
        "urgency": urgency,
        "entities": _entities(raw, catalog or []),
        "churn_signals": churn,
        "summary": _summary(sentiment, intent, concerns, urgency),
        "quote": quote,
        "source": "rules",
    }
