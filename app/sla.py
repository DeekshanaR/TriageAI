"""SLA tracking: due dates by priority and breach-risk detection."""
from datetime import datetime, timedelta, timezone

from app.config import SLA_AT_RISK_FRACTION, SLA_HOURS

FMT = "%Y-%m-%d %H:%M:%S"
FINAL = {"CLOSED", "CANCELLED"}
DONE = {"RESOLVED", "CLOSED"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def fmt(dt: datetime) -> str:
    return dt.strftime(FMT)


def parse(value: str) -> datetime:
    return datetime.strptime(value, FMT)


def due_for(priority: str, created: datetime) -> datetime:
    return created + timedelta(hours=SLA_HOURS.get(priority, SLA_HOURS["Medium"]))


def status(ticket: dict, now: datetime | None = None) -> dict:
    """state: ok | at_risk | breached | met | n/a   (+ minutes_left for open tickets)"""
    now = now or utcnow()
    if ticket["status"] == "CANCELLED" or not ticket.get("sla_due"):
        return {"state": "n/a", "minutes_left": None}
    created, due = parse(ticket["created_at"]), parse(ticket["sla_due"])
    if ticket["status"] in DONE:
        return {"state": "met" if parse(ticket["updated_at"]) <= due else "breached", "minutes_left": None}
    left = (due - now).total_seconds() / 60
    total = (due - created).total_seconds() / 60
    if left <= 0:
        state = "breached"
    elif left <= total * SLA_AT_RISK_FRACTION:
        state = "at_risk"
    else:
        state = "ok"
    return {"state": state, "minutes_left": round(left)}
