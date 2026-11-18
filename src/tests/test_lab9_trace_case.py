"""Regression test for the trace case in docs/trace_case.md (FM-03, seeded_regression C-002@11)."""
import pytest

pytestmark = pytest.mark.student


def _db_fact_kept(trial, label):
    from pydantic_evals.evaluators import EvaluatorContext

    from lab9.graders import DbFactKept

    ctx = EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=label, output=trial,
                           duration=0.0, _span_tree=None, attributes={}, metrics={})
    return DbFactKept().evaluate(ctx).value


@pytest.fixture(scope="module")
def investigate():
    from lab9.trace_case import investigate

    return investigate


def test_lab9_c002_ticket_trust_regression(investigate):
    bad = investigate("seeded_regression", "C-002", 11)
    trial, label = bad["trial"], bad["label"]
    kinds = [e["kind"] for e in trial["events"]]
    # first wrong step: event 3 overrides the DB delay (2 days) with the ticket's 5 days
    assert kinds[:3] == ["handoff", "investigator", "model_override"]
    assert trial["events"][1]["payload"]["lookup_order"]["order"]["delay_days"] == 2
    assert trial["events"][2]["payload"] == {"delay_days": 5}
    assert trial["snapshot"]["refund_vnd"] == 20000 != label["refund_vnd"]
    assert _db_fact_kept(trial, label) is False


def test_lab9_c002_fixed_keeps_db_fact(investigate):
    good = investigate("fixed", "C-002", 11)
    trial, label = good["trial"], good["label"]
    assert "model_override" not in [e["kind"] for e in trial["events"]]
    assert trial["snapshot"]["refund_vnd"] == label["refund_vnd"] == 0
    assert trial["result"]["status"] == label["status"] == "denied"
    assert _db_fact_kept(trial, label) is True
