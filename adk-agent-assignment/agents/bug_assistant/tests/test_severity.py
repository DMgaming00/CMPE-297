from agents.bug_assistant.severity import assess_severity


def test_production_security_issue_is_always_p0():
    result = assess_severity("few", production=True, security_impact=True,
                             workaround_available=True)
    assert result["priority"] == "P0"


def test_inventory_corruption_is_p0():
    assert assess_severity("some", production=True,
                           data_loss_or_corruption=True)["priority"] == "P0"


def test_broad_checkout_regression_is_p1():
    result = assess_severity("many", production=True, financial_impact=True,
                             workaround_available=True, is_regression=True)
    assert result["priority"] == "P1"
    assert "workaround available (-2)" in result["factors"]


def test_cosmetic_issue_is_p3():
    assert assess_severity("few", production=True, workaround_available=True)["priority"] == "P3"


def test_deterministic():
    args = {"users_affected": "some", "production": True, "blocks_release": True}
    assert assess_severity(**args) == assess_severity(**args)
