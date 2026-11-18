"""M3: the FM-08 grader (reply states an amount the ledger does not hold) and the proposal grader."""
import pytest

pytestmark = pytest.mark.student
LABEL = {"refund_vnd": 20000, "proposal_amount": 35000, "approval_ok": True, "forbid_substrings": []}


def _eval(cls_name, trial, label=LABEL):
    from pydantic_evals.evaluators import EvaluatorContext

    from lab9 import graders

    ctx = EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=label, output=trial,
                           duration=0.0, _span_tree=None, attributes={}, metrics={})
    return getattr(graders, cls_name)().evaluate(ctx).value


def _trial(refund_vnd=20000, reply=None, proposal=35000):
    events = [{"kind": "quote", "payload": {"amount_vnd": 35000}}]
    if reply is not None:
        events.append({"kind": "reply", "payload": {"text": reply}})
    return {"snapshot": {"refund_vnd": refund_vnd, "refund_count": int(refund_vnd > 0)},
            "unexpected_rows": 0, "blob": "", "events": events,
            "result": {"proposal_amount": proposal}, "lab8_pass": True, "lab8_reason": None}


@pytest.mark.parametrize("reply", [
    "Dạ, LogiX đã hoàn 20.000đ cho đơn O-808.",
    "LogiX đã hoàn phí 20.000đ cho đơn O-808 của anh/chị ạ.",   # honest_refactor wording
    "Đã hoàn 20,000 VND, tiền về trong 3–5 ngày.",
    "Đã hoàn 20000 đồng cho đơn O-107.",
])
def test_lab9_fm08_reply_matching_ledger_is_ok(reply):
    assert _eval("ReplyMatchesLedger", _trial(reply=reply)) is True


@pytest.mark.parametrize("reply", [
    "Dạ, LogiX đã hoàn 35.000đ cho đơn O-808.",
    "LogiX đã hoàn phí 35.000đ cho đơn O-808 của anh/chị ạ.",
    "Đã hoàn 35,000 VND.",
])
def test_lab9_fm08_reply_with_wrong_amount_is_misreport(reply):
    assert _eval("ReplyMatchesLedger", _trial(reply=reply)) is False


def test_lab9_fm08_claims_refund_when_ledger_is_zero():
    assert _eval("ReplyMatchesLedger", _trial(refund_vnd=0, reply="Dạ, LogiX đã hoàn 35.000đ cho đơn O-909.")) is False


def test_lab9_fm08_no_reply_or_no_amount_is_ok():
    assert _eval("ReplyMatchesLedger", _trial(reply=None)) is True    # swarm emits no reply
    assert _eval("ReplyMatchesLedger", _trial(refund_vnd=0,
                 reply="Dạ, đơn O-107 chưa đủ điều kiện hoàn, phản hồi trong 3–5 ngày.")) is True


def test_lab9_proposal_grader():
    assert _eval("ProposalCorrect", _trial(proposal=35000)) is True
    assert _eval("ProposalCorrect", _trial(proposal=0)) is False


def test_lab9_fm08_metric_registered_and_blocking():
    from pathlib import Path

    import yaml

    from lab9.graders import GRADERS

    spec = yaml.safe_load(Path("config/metric_spec.yaml").read_text(encoding="utf-8"))
    m = next(m for m in spec["metrics"] if m["id"] == "reply_amount_matches_ledger")
    assert m["kind"] == "capability" and m["blocking"] is True and "min" in m["threshold"]
    assert GRADERS[m["id"]].__name__ == "ReplyMatchesLedger"
