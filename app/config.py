"""Central configuration. Values can be overridden with environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "sample_tickets.csv"
MODEL_PATH = BASE_DIR / "models" / "ticket_classifier.joblib"


def db_path() -> str:
    # Read at call time so tests can point to a temporary database.
    return os.getenv("TICKET_DB", str(BASE_DIR / "tickets.db"))


# Which team handles which category (simple routing rules).
ASSIGNMENT_RULES = {
    "Network": "network-team",
    "Access": "iam-team",
    "Hardware": "desktop-support",
    "Software": "app-support",
    "Email": "messaging-team",
    "Security": "security-team",
}

# Below this confidence the ticket is flagged for manual triage.
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.45"))

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")


# ---------- v2: autonomy, correlation, SLA ----------
def model_path():
    """Model location; override with TICKET_MODEL (used by tests)."""
    return Path(os.getenv("TICKET_MODEL", str(MODEL_PATH)))


# Risk of automatically acting on a category.
RISK_BY_CATEGORY = {
    "Security": "critical",   # always human
    "Access": "high",         # permission changes need approval
    "Network": "medium",
    "Email": "medium",
    "Hardware": "low",
    "Software": "low",
}
AUTO_CONFIDENCE = float(os.getenv("AUTO_CONFIDENCE", "0.65"))   # >= this -> may act automatically

SLA_HOURS = {"High": 4, "Medium": 8, "Low": 24}
SLA_AT_RISK_FRACTION = 0.25          # last 25% of the SLA window = "at risk"

# Incident-storm correlation
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.55"))
INCIDENT_WINDOW_MIN = int(os.getenv("INCIDENT_WINDOW_MIN", "30"))
INCIDENT_MIN_TICKETS = int(os.getenv("INCIDENT_MIN_TICKETS", "3"))

RETRAIN_WEIGHT = 5   # each human correction counts this many times in retraining
