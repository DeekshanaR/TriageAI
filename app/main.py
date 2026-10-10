"""FastAPI REST API. Run with:  uvicorn app.main:app --reload
Interactive docs are served at http://127.0.0.1:8000/docs
"""
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from app import service
from app.lifecycle import InvalidTransition

app = FastAPI(title="Self-Governing AI Ticket Agent", version="2.0.0")


class TicketIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5)


class TransitionIn(BaseModel):
    status: str
    note: str = ""


class ApproveIn(BaseModel):
    note: str = ""


class CorrectIn(BaseModel):
    category: str
    priority: str | None = None
    note: str = ""


def _guard(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except service.TicketNotFound as exc:
        raise HTTPException(404, str(exc))
    except (InvalidTransition, service.InvalidOperation) as exc:
        raise HTTPException(409, str(exc))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/tickets", status_code=201)
def create_ticket(body: TicketIn):
    return service.create_ticket(body.title, body.description)


@app.get("/tickets")
def list_tickets(status: str | None = Query(None), category: str | None = Query(None)):
    return service.list_tickets(status, category)


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int):
    return _guard(service.get_ticket, ticket_id)


@app.post("/tickets/{ticket_id}/transition")
def transition(ticket_id: int, body: TransitionIn):
    return _guard(service.transition, ticket_id, body.status.upper(), body.note)


@app.get("/tickets/{ticket_id}/history")
def ticket_history(ticket_id: int):
    return _guard(service.history, ticket_id)


@app.post("/tickets/{ticket_id}/approve")
def approve(ticket_id: int, body: ApproveIn):
    """Human approves the AI's proposed routing."""
    return _guard(service.approve, ticket_id, body.note)


@app.post("/tickets/{ticket_id}/correct")
def correct(ticket_id: int, body: CorrectIn):
    """Human corrects the category/priority. Stored for the next retraining."""
    return _guard(service.correct, ticket_id, body.category, body.priority, body.note)


@app.get("/approvals")
def approvals():
    return service.pending_approvals()


@app.get("/incidents")
def incidents():
    return service.incidents()


@app.get("/sla/at-risk")
def sla_at_risk():
    return service.sla_at_risk()


@app.post("/model/retrain")
def retrain():
    return service.retrain()


@app.get("/stats")
def stats():
    return service.stats()
