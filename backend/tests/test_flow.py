EXPECTED = {
    "Priya Nair": ("retention_call", "High", "Negative"),
    "James Okonkwo": ("resolve_complaint", "High", "Negative"),
    "Mei Chen": ("offer_renewal", "High", "Positive"),
    "Arjun Mehta": ("offer_product", "Medium", "Positive"),
    "Elena Vasquez": ("retention_call", "High", "Negative"),
    "Daniel Brooks": ("no_action", "None", "Positive"),
    "Sofia Alvarez": ("payment_follow_up", "High", "Negative"),
    "Robert Hale": ("escalate_service", "High", "Negative"),
    "Aisha Rahman": ("schedule_follow_up", "High", "Negative"),
    "Liam Murphy": ("offer_product", "Medium", "Positive"),
    "Hannah Berg": ("follow_up_claim", "Low", "Neutral"),
    "Kenji Sato": ("no_action", "None", "Positive"),
    "Fatima Diallo": ("no_action", "None", "Positive"),
    "Oliver Grant": ("no_action", "None", "Positive"),
    "Nina Kowalski": ("schedule_follow_up", "Medium", "Positive"),
    "Carlos Mendes": ("retention_call", "High", "Neutral"),
    "Grace Adeyemi": ("no_action", "None", "Positive"),
    "Wei Zhang": ("offer_product", "Medium", "Neutral"),
    "Noah Williams": ("offer_product", "Medium", "Positive"),
    "Isabella Rossi": ("no_action", "None", "Positive"),
    "Samuel Boateng": ("schedule_follow_up", "Medium", "Neutral"),
    "Chloe Martin": ("offer_product", "Medium", "Positive"),
    "David Kim": ("payment_follow_up", "Medium", "Neutral"),
    "Amara Singh": ("no_action", "None", "Positive"),
    "Thomas Berger": ("personalized_discount", "High", "Negative"),
    "Leila Haddad": ("schedule_follow_up", "Medium", "Neutral"),
    "Patrick O'Brien": ("no_action", "None", "Neutral"),
    "Yuki Tanaka": ("escalate_service", "High", "Neutral"),
}


def _by_name(client):
    response = client.get("/api/customers")
    assert response.status_code == 200
    return {row["name"]: row for row in response.json()["customers"]}


def test_book_and_health(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["ai_mode"] == "rules"
    assert body["customers"] == 28

    dashboard = client.get("/api/dashboard").json()
    assert dashboard["kpis"]["customers"] == 28
    assert len(dashboard["stories"]) == 6
    assert dashboard["kpis"]["high_risk"] >= 4
    assert dashboard["kpis"]["needs_action"] >= 8
    assert dashboard["kpis"]["open_issues"] >= 8
    assert {point["label"] for point in dashboard["charts"]["sentiment"]} == {"Positive", "Neutral", "Negative"}


def test_every_customer_recommendation(client):
    rows = _by_name(client)
    assert set(rows) == set(EXPECTED)
    for name, (action, priority, sentiment) in EXPECTED.items():
        row = rows[name]
        assert row["nba"]["action_type"] == action, (name, row["nba"]["title"], row["nba"]["action_type"], row["sentiment"], row["risk_level"])
        assert row["nba"]["priority"] == priority, (name, row["nba"])
        assert row["sentiment"] == sentiment, (name, row["sentiment"], row["intent"])
        assert row["nba"]["reason"]
        assert row["nba"]["evidence_preview"]

    priya = rows["Priya Nair"]
    daniel = rows["Daniel Brooks"]
    assert priya["risk_level"] == "High"
    assert daniel["risk_level"] == "Low"
    assert rows["Elena Vasquez"]["risk_level"] == "Medium"


def test_priya_file_explains_itself(client):
    priya = _by_name(client)["Priya Nair"]
    detail = client.get(f"/api/customers/{priya['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["nba"]["action_type"] == "retention_call"
    assert any("CLM-3391" in item for item in body["nba"]["evidence"])
    assert body["nba"]["reasoning"]
    assert "an affluent" in body["insights"]["summary"]
    assert "Onboarding is confusing" not in body["insights"]["concerns"]
    assert "switching" in body["insights"]["summary"].lower() or any("switch" in item.lower() for item in body["nba"]["evidence"])
    assert any(item["kind"] == "Call" and item["ai"] for item in body["timeline"])
    call = next(item for item in body["timeline"] if item["kind"] == "Call" and item["sentiment"] == "Negative")
    assert call["intent"]
    assert call["quote"]
    assert "CLM-3391" in call["entities"] or "CLM-3391" in call["detail"]


def test_questions_recommend_an_action(client):
    priya = _by_name(client)["Priya Nair"]["id"]
    daniel = _by_name(client)["Daniel Brooks"]["id"]
    for question in [
        "Why is this customer at risk?",
        "What should we do next?",
        "Why is the customer unhappy?",
        "Should we contact this customer?",
        "Summarize this customer's recent interactions.",
        "What product would be relevant for this customer?",
    ]:
        response = client.post(f"/api/customers/{priya}/ask", json={"question": question})
        assert response.status_code == 200, question
        answer = response.json()
        assert answer["source"] == "rules"
        assert "Recommended action:" in answer["answer"]
        assert answer["recommended_action"]

    contact = client.post(f"/api/customers/{daniel}/ask", json={"question": "Should we contact this customer?"})
    assert contact.json()["answer"].startswith("No.")


def test_record_action_and_resolve_case(client):
    priya = _by_name(client)["Priya Nair"]["id"]
    saved = client.post(
        f"/api/customers/{priya}/actions",
        json={
            "action_type": "retention_call",
            "title": "Call with a renewal plan and close the open claim first",
            "outcome": "Completed",
            "note": "Acknowledged CLM-3391 and promised a decision date.",
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["actions"][0]["outcome"] == "Completed"
    assert any(item["kind"] == "Action" for item in body["timeline"])

    hannah = client.get("/api/customers/CUS-1182").json()
    case_id = next(case["id"] for case in hannah["cases"] if case["status"] in {"Open", "In Progress"})
    updated = client.patch(f"/api/cases/{case_id}", json={"status": "Resolved"})
    assert updated.status_code == 200
    assert updated.json()["nba"]["action_type"] != "follow_up_claim"


def test_evidence_confidence_alternatives_and_outcome(client):
    priya = client.get("/api/customers/CUS-1042").json()
    links = priya["nba"]["evidence_links"]
    assert links
    assert all(item["timeline_id"] for item in links)
    claim = next(item for item in links if "CLM-3391" in item["text"])
    assert claim["timeline_id"] == "case-open-CLM-3391"
    assert 64 <= priya["nba"]["confidence"] <= 96
    assert "signals" in priya["nba"]["confidence_note"]
    assert "data source" in priya["nba"]["confidence_note"]
    assert "highest-priority" in priya["nba"]["selection"]
    assert 2 <= len(priya["nba"]["alternatives"]) <= 3
    assert any("Discount skipped" in item["reason"] for item in priya["nba"]["alternatives"])
    assert priya["sources"]["analyzed_interactions"] >= 1
    assert any(item["name"] == "Claims" and item["count"] >= 1 for item in priya["sources"]["items"])
    assert any(item["id"].startswith("product-") for item in priya["timeline"])
    assert any(item["id"].startswith("pay-") for item in priya["timeline"])

    daniel = client.get("/api/customers/CUS-1175").json()
    assert daniel["nba"]["action_type"] == "no_action"
    assert 2 <= len(daniel["nba"]["alternatives"]) <= 3

    saved = client.post(
        "/api/customers/CUS-1042/actions",
        json={
            "action_type": "retention_call",
            "title": "Call with a renewal plan and close the open claim first",
            "outcome": "Completed",
            "note": "Customer agreed to stay through renewal.",
            "owner": "Helena Ortiz",
            "due_on": "2026-10-08",
            "priority": "High",
            "result": "Customer retained",
        },
    )
    assert saved.status_code == 200
    action = saved.json()["actions"][0]
    assert action["owner"] == "Helena Ortiz"
    assert action["priority"] == "High"
    assert action["due_on"] == "2026-10-08"
    assert action["result"] == "Customer retained"
    assert action["risk_before"] == "High"
    assert action["risk_after"] == "Medium"
    assert saved.json()["risk"]["level"] == "Medium"
    assert any(item["kind"] == "Action" and "Helena Ortiz" in item["detail"] for item in saved.json()["timeline"])

    mei = client.post(
        "/api/customers/CUS-1088/actions",
        json={
            "action_type": "offer_renewal",
            "title": "Renewal completed on the call",
            "outcome": "Completed",
            "owner": "Samir Shah",
            "priority": "High",
            "result": "Renewal completed",
        },
    )
    assert mei.status_code == 200
    assert mei.json()["nba"]["action_type"] != "offer_renewal"
    assert mei.json()["actions"][0]["nba_before"] != mei.json()["actions"][0]["nba_after"]


def test_render_postgres_url(monkeypatch):
    from app.database import database_url

    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@dpg-abc-a/customer360")
    assert database_url() == "postgresql+psycopg://user:pass@dpg-abc-a/customer360"
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@dpg-abc.oregon-postgres.render.com/customer360")
    external = database_url()
    assert external.startswith("postgresql+psycopg://")
    assert "sslmode=require" in external


def test_search_filters_and_reread(client):
    found = client.get("/api/customers", params={"q": "CLM-3391"}).json()["customers"]
    assert len(found) == 1
    assert found[0]["name"] == "Priya Nair"
    high = client.get("/api/customers", params={"risk": "High"}).json()["customers"]
    assert high
    assert all(row["risk_level"] == "High" for row in high)
    reread = client.post("/api/customers/CUS-1042/analyze")
    assert reread.status_code == 200
    assert reread.json()["insights"]["sentiment"] == "Negative"
    assert reread.json()["insights"]["source"] == "rules"
