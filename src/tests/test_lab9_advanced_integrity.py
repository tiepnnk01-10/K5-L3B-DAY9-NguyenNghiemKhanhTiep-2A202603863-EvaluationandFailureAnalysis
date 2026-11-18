"""M7 extra integrity checks beyond the public traps (hidden-trap candidates from CHECKPOINTS.md)."""
import copy

import pytest

pytestmark = pytest.mark.student

ROWS = [{"item_id": f"E-{i:03d}", "seed": s, "pass_rate": i != 3 or s != 1,
         "slices": ["money_movement"] if i < 2 else []}
        for i in range(4) for s in (1, 2)]
SPEC = {"eval_set_version": "v2", "bootstrap": {"n_resamples": 200, "rng": 1},
        "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True,
                     "threshold": {"min": 0.8, "no_significant_drop": True}}],
        "slices": [{"name": "money_movement", "metric": "pass_rate", "min": 0.9, "blocking": True}]}


def _report(rows, metrics=None, items=4, seeds=(1, 2), failures=()):
    from lab9.eval import aggregate

    metrics = metrics if metrics is not None else aggregate([{**r, "cost": 1.0} for r in rows], ["pass_rate"])
    return {"manifest": {"eval_set_sha": "x", "items": items, "seeds": list(seeds)},
            "rows": rows, "metrics": metrics, "evaluator_failures": list(failures)}


@pytest.fixture
def gate():
    from lab9 import gate

    return gate


@pytest.fixture
def base():
    return _report(copy.deepcopy(ROWS))


def test_advanced_clean_report_is_trusted(gate, base):
    assert gate.integrity_check(base, base, SPEC, SPEC) == []


def test_advanced_duplicate_rows_replace_a_failure(gate, base):
    rows = copy.deepcopy(ROWS)
    rows[-2] = copy.deepcopy(rows[-1])            # E-003@1 (fail) replaced by a copy of E-003@2 (pass)
    assert any("duplicated" in p for p in gate.integrity_check(_report(rows), base, SPEC))


def test_advanced_evaluator_failures_on_a_green_run(gate, base):
    green = _report(copy.deepcopy(ROWS), failures=["E-000@1:RefundAmountCorrect:boom"])
    assert any("evaluator failure" in p for p in gate.integrity_check(green, base, SPEC))


def test_advanced_metrics_must_match_rows(gate, base):
    edited = _report(copy.deepcopy(ROWS), metrics={"pass_rate": 1.0})   # rows say 0.875
    assert any("rows give" in p for p in gate.integrity_check(edited, base, SPEC))


def test_advanced_renamed_eval_set_version_still_ratchets(gate, base):
    loose = copy.deepcopy(SPEC)
    loose["eval_set_version"] = "v2b"
    loose["metrics"][0]["threshold"]["min"] = 0.5
    problems = gate.integrity_check(base, base, loose, SPEC)
    assert any("min 0.8 -> 0.5" in p for p in problems)
    assert any("eval_set_version" in p for p in problems)


def test_advanced_slice_ratchet_and_removed_slice(gate, base):
    loose = copy.deepcopy(SPEC)
    loose["slices"][0]["min"] = 0.5
    assert any("slice money_movement" in p for p in gate.integrity_check(base, base, loose, SPEC))
    gone = copy.deepcopy(SPEC)
    gone["slices"] = []
    assert any("removed" in p for p in gate.integrity_check(base, base, gone, SPEC))


def test_advanced_slice_tags_relabelled_or_inconsistent(gate, base):
    moved = copy.deepcopy(ROWS)
    for r in moved:
        if r["item_id"] == "E-000":
            r["slices"] = []
    assert any("slice tags" in p for p in gate.integrity_check(_report(moved), base, SPEC))
    mixed = copy.deepcopy(ROWS)
    mixed[0]["slices"] = []                       # E-000@1 loses its tag, E-000@2 keeps it
    assert any("across seeds" in p for p in gate.integrity_check(_report(mixed), base, SPEC))


def test_advanced_empty_slice_blocks(gate, base):
    rows = copy.deepcopy(ROWS)
    for r in rows:
        r["slices"] = []
    blocked, _ = gate.slice_check(_report(rows), base, SPEC)
    assert blocked == ["slice:money_movement/pass_rate"]
