from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create(title, desc):
    r = client.post("/tickets", json={"title": title, "description": desc})
    assert r.status_code == 201
    return r.json()


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_full_lifecycle_and_history():
    t = _create("Printer not printing", "Office printer shows offline and jobs are stuck in queue")
    assert t["status"] == "ASSIGNED"
    for status in ("IN_PROGRESS", "RESOLVED", "CLOSED"):
        assert client.post(f"/tickets/{t['id']}/transition", json={"status": status}).status_code == 200
    history = client.get(f"/tickets/{t['id']}/history").json()
    assert [h["to_status"] for h in history] == ["NEW", "TRIAGED", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED"]


def test_invalid_transition_returns_409():
    t = _create("Printer not printing", "Office printer shows offline and jobs are stuck in queue")
    assert client.post(f"/tickets/{t['id']}/transition", json={"status": "CLOSED"}).status_code == 409


def test_not_found_and_validation():
    assert client.get("/tickets/9999").status_code == 404
    assert client.post("/tickets", json={"title": "x", "description": "y"}).status_code == 422


def test_approval_flow_over_http():
    t = _create("Account locked", "My account got locked after several failed login attempts")
    assert t["autonomy"] == "APPROVAL"
    assert [x["id"] for x in client.get("/approvals").json()] == [t["id"]]
    r = client.post(f"/tickets/{t['id']}/approve", json={"note": "ok"})
    assert r.status_code == 200 and r.json()["assignee"] == "iam-team"
    assert client.post(f"/tickets/{t['id']}/approve", json={}).status_code == 409


def test_correct_endpoint_and_bad_category():
    t = _create("Excel freezing", "Spreadsheet application hangs when opening large workbook")
    assert client.post(f"/tickets/{t['id']}/correct", json={"category": "Nonsense"}).status_code == 409
    r = client.post(f"/tickets/{t['id']}/correct", json={"category": "Hardware"})
    assert r.status_code == 200 and r.json()["assignee"] == "desktop-support"


def test_stats_include_governance_numbers():
    _create("Ransomware message", "Files are encrypted and a ransom note appeared on the desktop")
    _create("Excel freezing", "Spreadsheet application hangs when opening large workbook")
    s = client.get("/stats").json()
    assert s["pending_human_review"] == 1
    assert 0 < s["automation_rate"] < 1
    assert client.get("/incidents").json() == []
    assert client.get("/sla/at-risk").status_code == 200
