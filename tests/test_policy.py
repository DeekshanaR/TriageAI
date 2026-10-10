from app.policy import decide


def test_security_is_always_manual():
    assert decide("Security", "High", 0.99, False)["level"] == "MANUAL"


def test_injection_forces_manual():
    assert decide("Software", "Low", 0.99, True)["level"] == "MANUAL"


def test_low_confidence_is_manual():
    assert decide("Software", "Low", 0.2, False)["level"] == "MANUAL"


def test_access_needs_approval_even_when_confident():
    assert decide("Access", "Medium", 0.99, False)["level"] == "APPROVAL"


def test_moderate_confidence_needs_approval():
    assert decide("Hardware", "Low", 0.55, False)["level"] == "APPROVAL"


def test_confident_low_risk_is_automatic():
    assert decide("Hardware", "Low", 0.95, False)["level"] == "AUTO"
