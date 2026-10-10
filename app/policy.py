"""Autonomy policy: decides how much the system may do WITHOUT a human.

AUTO     - route automatically (low risk, high confidence)
APPROVAL - propose a route, wait for a human to approve (medium confidence or sensitive category)
MANUAL   - human only (security tickets, low confidence, suspicious text)

The point: automation that knows its limits. Wrongly auto-routing a phishing
report or a permissions request is far more costly than a slower approval.
"""
from app.config import AUTO_CONFIDENCE, CONFIDENCE_THRESHOLD, RISK_BY_CATEGORY


def decide(category: str, priority: str, confidence: float, injection_suspected: bool) -> dict:
    risk = RISK_BY_CATEGORY.get(category, "medium")
    if injection_suspected:
        return {"level": "MANUAL", "risk": "critical",
                "reason": "Possible prompt-injection text; sent to a human, LLM skipped"}
    if risk == "critical":
        return {"level": "MANUAL", "risk": risk, "reason": f"{category} tickets always need a human"}
    if confidence < CONFIDENCE_THRESHOLD:
        return {"level": "MANUAL", "risk": risk,
                "reason": f"Low model confidence ({confidence:.0%} < {CONFIDENCE_THRESHOLD:.0%})"}
    if risk == "high":
        return {"level": "APPROVAL", "risk": risk, "reason": f"{category} changes need human approval"}
    if confidence < AUTO_CONFIDENCE:
        return {"level": "APPROVAL", "risk": risk,
                "reason": f"Moderate confidence ({confidence:.0%} < {AUTO_CONFIDENCE:.0%})"}
    return {"level": "AUTO", "risk": risk, "reason": f"High confidence ({confidence:.0%}), {risk} risk"}
