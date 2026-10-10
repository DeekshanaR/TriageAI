"""Business logic shared by the REST API, the batch runner and the demo."""
import json
import logging
from datetime import datetime, timedelta

from app import ai_assistant, guard, policy, similarity, sla
from app.classifier import get_classifier, reset as reset_classifier, train
from app.config import (ASSIGNMENT_RULES, INCIDENT_MIN_TICKETS, INCIDENT_WINDOW_MIN,
                        SIMILARITY_THRESHOLD, SLA_HOURS)
from app.database import get_conn
from app.lifecycle import validate_transition

log = logging.getLogger(__name__)
JSON_FIELDS = ("injection_flags", "explanation", "similar_ids")


class TicketNotFound(LookupError):
    pass


class InvalidOperation(ValueError):
    """The ticket is not in a state where this action makes sense."""


# ---------------------------------------------------------------- helpers
def _row(row) -> dict:
    data = dict(row)
    for key in JSON_FIELDS:
        data[key] = json.loads(data[key] or "[]")
    return data


def _record(conn, ticket_id, from_status, to_status, note):
    conn.execute(
        "INSERT INTO ticket_history (ticket_id, from_status, to_status, note) VALUES (?,?,?,?)",
        (ticket_id, from_status, to_status, note),
    )


def _insert(conn, now: datetime, **f) -> int:
    created = sla.fmt(now)
    cur = conn.execute(
        """INSERT INTO tickets (title, description, category, priority, confidence, needs_review,
               ai_suggestion, autonomy, risk, policy_reason, approval_status, injection_flags,
               explanation, similar_ids, is_incident, sla_due, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (f["title"], f["description"], f["category"], f["priority"], f.get("confidence"),
         f.get("needs_review", 0), f.get("ai_suggestion"), f["autonomy"], f["risk"], f["policy_reason"],
         f.get("approval_status"), json.dumps(f.get("injection_flags", [])),
         json.dumps(f.get("explanation", [])), json.dumps(f.get("similar_ids", [])),
         f.get("is_incident", 0), sla.fmt(sla.due_for(f["priority"], now)), created, created),
    )
    return cur.lastrowid


# ---------------------------------------------------------------- queries
def get_ticket(ticket_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not row:
        raise TicketNotFound(f"Ticket {ticket_id} not found")
    return _row(row)


def list_tickets(status: str | None = None, category: str | None = None) -> list[dict]:
    query, params = "SELECT * FROM tickets WHERE 1=1", []
    if status:
        query += " AND status = ?"
        params.append(status)
    if category:
        query += " AND category = ?"
        params.append(category)
    with get_conn() as conn:
        return [_row(r) for r in conn.execute(query + " ORDER BY id DESC", params)]


def history(ticket_id: int) -> list[dict]:
    get_ticket(ticket_id)
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM ticket_history WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall()
    return [dict(r) for r in rows]


def pending_approvals() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM tickets WHERE status = 'TRIAGED' AND is_incident = 0
               AND (approval_status = 'PENDING' OR needs_review = 1) ORDER BY id""").fetchall()
    return [_row(r) for r in rows]


def incidents() -> list[dict]:
    with get_conn() as conn:
        parents = conn.execute("SELECT * FROM tickets WHERE is_incident = 1 ORDER BY id DESC").fetchall()
        out = []
        for p in parents:
            kids = conn.execute("SELECT id, title, status FROM tickets WHERE parent_id = ? ORDER BY id", (p["id"],)).fetchall()
            out.append({**_row(p), "children": [dict(k) for k in kids]})
    return out


def sla_at_risk(now: datetime | None = None) -> list[dict]:
    now = now or sla.utcnow()
    result = []
    for t in list_tickets():
        if t["status"] in sla.FINAL or t["status"] in sla.DONE:
            continue
        info = sla.status(t, now)
        if info["state"] in ("at_risk", "breached"):
            result.append({"id": t["id"], "title": t["title"], "priority": t["priority"],
                           "assignee": t["assignee"], "sla_due": t["sla_due"], **info})
    return sorted(result, key=lambda r: r["minutes_left"])


# ---------------------------------------------------------------- lifecycle
def transition(ticket_id: int, new_status: str, note: str = "", now: datetime | None = None) -> dict:
    ticket = get_ticket(ticket_id)
    validate_transition(ticket["status"], new_status)
    with get_conn() as conn:
        conn.execute("UPDATE tickets SET status = ?, updated_at = ? WHERE id = ?",
                     (new_status, sla.fmt(now or sla.utcnow()), ticket_id))
        _record(conn, ticket_id, ticket["status"], new_status, note)
    return get_ticket(ticket_id)


def _assign(ticket_id: int, category: str, note: str, now=None) -> dict:
    team = ASSIGNMENT_RULES.get(category, "service-desk")
    with get_conn() as conn:
        conn.execute("UPDATE tickets SET assignee = ? WHERE id = ?", (team, ticket_id))
    return transition(ticket_id, "ASSIGNED", f"{note} -> {team}", now)


# ---------------------------------------------------------------- incident correlation
def _recent_open(now: datetime) -> list[dict]:
    cutoff = sla.fmt(now - timedelta(minutes=INCIDENT_WINDOW_MIN))
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM tickets WHERE is_incident = 0 AND status NOT IN ('CLOSED','CANCELLED')
               AND created_at >= ? ORDER BY id DESC LIMIT 200""", (cutoff,)).fetchall()
    return [_row(r) for r in rows]


def _correlate(ticket_id: int, title: str, category: str, similar_same: list[dict], now: datetime):
    """If enough similar tickets arrived recently, group them under one major incident."""
    if len(similar_same) + 1 < INCIDENT_MIN_TICKETS:
        return None
    parent_id = next((t["parent_id"] for t in similar_same if t["parent_id"]), None)
    if parent_id is None:
        with get_conn() as conn:
            parent_id = _insert(
                conn, now, title=f"[MAJOR INCIDENT] {category}: {title}",
                description=f"Auto-created: {len(similar_same) + 1} similar {category} tickets within "
                            f"{INCIDENT_WINDOW_MIN} minutes.",
                category=category, priority="High", confidence=None, autonomy="MANUAL", risk="high",
                policy_reason="Correlated ticket storm; needs an incident manager", is_incident=1)
            _record(conn, parent_id, None, "NEW", "Incident auto-created by correlation engine")
        transition(parent_id, "TRIAGED", "Correlated from similar tickets", now)
        _assign(parent_id, category, "Incident escalated", now)
    to_link = [t["id"] for t in similar_same if not t["parent_id"]] + [ticket_id]
    with get_conn() as conn:
        for tid in to_link:
            conn.execute("UPDATE tickets SET parent_id = ? WHERE id = ?", (parent_id, tid))
            current = conn.execute("SELECT status FROM tickets WHERE id = ?", (tid,)).fetchone()[0]
            _record(conn, tid, current, current, f"Linked to major incident #{parent_id}")
    return parent_id


# ---------------------------------------------------------------- main entry point
def create_ticket(title: str, description: str, now: datetime | None = None) -> dict:
    """Create a ticket: guard -> classify -> explain -> policy -> correlate -> (maybe) assign."""
    now = now or sla.utcnow()
    text = f"{title} {description}"
    flags = guard.detect_injection(text)
    clf = get_classifier()
    pred = clf.predict(title, description)
    decision = policy.decide(pred["category"], pred["priority"], pred["confidence"], bool(flags))
    suggestion = ai_assistant.suggest_resolution(title, description, pred["category"], allow_llm=not flags)
    similar = [] if flags else similarity.find_similar(text, _recent_open(now), SIMILARITY_THRESHOLD)

    with get_conn() as conn:
        ticket_id = _insert(
            conn, now, title=title, description=description, category=pred["category"],
            priority=pred["priority"], confidence=pred["confidence"],
            needs_review=int(decision["level"] == "MANUAL"), ai_suggestion=suggestion,
            autonomy=decision["level"], risk=decision["risk"], policy_reason=decision["reason"],
            approval_status="PENDING" if decision["level"] == "APPROVAL" else None,
            injection_flags=flags, explanation=clf.explain(title, description),
            similar_ids=[{"id": s["id"], "score": s["score"]} for s in similar])
        _record(conn, ticket_id, None, "NEW", "Ticket created")
    transition(ticket_id, "TRIAGED",
               f"AI: {pred['category']} ({pred['confidence']:.0%}); policy {decision['level']}: {decision['reason']}", now)

    same_category = [s for s in similar if s["category"] == pred["category"]]
    _correlate(ticket_id, title, pred["category"], same_category, now)

    if decision["level"] == "AUTO":
        _assign(ticket_id, pred["category"], "Auto-assigned", now)
    else:
        log.info("Ticket %s waits for a human (%s)", ticket_id, decision["level"])
    return get_ticket(ticket_id)


# ---------------------------------------------------------------- human-in-the-loop
def approve(ticket_id: int, note: str = "") -> dict:
    t = get_ticket(ticket_id)
    if t["status"] != "TRIAGED" or not (t["approval_status"] == "PENDING" or t["needs_review"]):
        raise InvalidOperation("Ticket is not waiting for human review")
    with get_conn() as conn:
        conn.execute("UPDATE tickets SET approval_status = 'APPROVED', needs_review = 0 WHERE id = ?", (ticket_id,))
    return _assign(ticket_id, t["category"], f"Approved by human. {note}".strip())


def correct(ticket_id: int, category: str, priority: str | None = None, note: str = "") -> dict:
    """Human fixes the AI's category. The correction is stored for retraining."""
    if category not in ASSIGNMENT_RULES:
        raise InvalidOperation(f"Unknown category '{category}'. Valid: {sorted(ASSIGNMENT_RULES)}")
    if priority and priority not in SLA_HOURS:
        raise InvalidOperation(f"Unknown priority '{priority}'. Valid: {sorted(SLA_HOURS)}")
    t = get_ticket(ticket_id)
    if t["status"] not in ("TRIAGED", "ASSIGNED"):
        raise InvalidOperation("Only TRIAGED or ASSIGNED tickets can be re-routed")
    new_priority = priority or t["priority"]
    team = ASSIGNMENT_RULES[category]
    with get_conn() as conn:
        if category != t["category"] or new_priority != t["priority"]:
            conn.execute(
                """INSERT INTO corrections (ticket_id, title, description, predicted_category,
                       correct_category, correct_priority) VALUES (?,?,?,?,?,?)""",
                (ticket_id, t["title"], t["description"], t["category"], category, new_priority))
        due = sla.fmt(sla.due_for(new_priority, sla.parse(t["created_at"])))
        conn.execute(
            """UPDATE tickets SET category = ?, priority = ?, assignee = ?, sla_due = ?,
                   approval_status = 'CORRECTED', needs_review = 0 WHERE id = ?""",
            (category, new_priority, team, due, ticket_id))
        if t["status"] == "ASSIGNED":
            _record(conn, ticket_id, "ASSIGNED", "ASSIGNED", f"Re-routed by human to {team}. {note}".strip())
    if t["status"] == "TRIAGED":
        return transition(ticket_id, "ASSIGNED", f"Routed by human correction -> {team}. {note}".strip())
    return get_ticket(ticket_id)


def retrain() -> dict:
    """Retrain the model from the base data plus every stored human correction."""
    with get_conn() as conn:
        rows = conn.execute("SELECT title, description, correct_category, correct_priority FROM corrections").fetchall()
    extra = [{"title": r["title"], "description": r["description"],
              "category": r["correct_category"], "priority": r["correct_priority"]} for r in rows]
    scores = train(extra_rows=extra, verbose=False)
    reset_classifier()
    return {"corrections_used": len(extra), "clean_holdout_accuracy": scores}


# ---------------------------------------------------------------- reporting
def stats() -> dict:
    with get_conn() as conn:
        def group(col):
            return {r[0]: r[1] for r in conn.execute(f"SELECT {col}, COUNT(*) FROM tickets GROUP BY {col}")}
        by_status, by_category, by_priority = group("status"), group("category"), group("priority")
        normal = conn.execute("SELECT COUNT(*) FROM tickets WHERE is_incident = 0").fetchone()[0]
        auto = conn.execute("SELECT COUNT(*) FROM tickets WHERE is_incident = 0 AND autonomy = 'AUTO'").fetchone()[0]
        flagged = conn.execute("SELECT COUNT(*) FROM tickets WHERE injection_flags != '[]'").fetchone()[0]
        corrections = conn.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
        major = conn.execute("SELECT COUNT(*) FROM tickets WHERE is_incident = 1").fetchone()[0]
        by_autonomy = {r[0]: r[1] for r in conn.execute(
            "SELECT autonomy, COUNT(*) FROM tickets WHERE is_incident = 0 GROUP BY autonomy")}
    return {
        "by_status": by_status, "by_category": by_category, "by_priority": by_priority,
        "by_autonomy": by_autonomy,
        "automation_rate": round(auto / normal, 3) if normal else 0.0,
        "pending_human_review": len(pending_approvals()),
        "major_incidents": major, "injection_attempts_flagged": flagged,
        "human_corrections": corrections, "sla_at_risk_or_breached": len(sla_at_risk()),
    }
