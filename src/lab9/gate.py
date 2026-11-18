"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)
    Also caught (hidden traps): duplicated (item_id, seed) rows, an item whose slice tags differ
    between seeds, evaluator failures or NaN in the baseline, aggregate metrics that do not match
    the rows they claim to summarise, and bootstrap settings changed in the same PR."""
    from lab9.graders import GRADERS

    problems: list[str] = []
    graded = [m["id"] for m in spec.get("metrics", []) if m["id"] in GRADERS]

    for name, rep in (("PR", pr), ("baseline", base)):
        for k, v in (rep.get("metrics") or {}).items():
            if isinstance(v, float) and not math.isfinite(v):
                problems.append(f"{name} metric {k} is {v}")
        if rep.get("evaluator_failures"):
            problems.append(f"{name} has {len(rep['evaluator_failures'])} evaluator failure(s), "
                            f"first: {rep['evaluator_failures'][0]}")

    rows, brows = pr.get("rows") or [], base.get("rows") or []
    man = pr.get("manifest") or {}
    want = (man.get("items") or 0) * len(man.get("seeds") or [])
    if len(rows) != want:
        problems.append(f"{len(rows)} rows, manifest promises {man.get('items')} items x {len(man.get('seeds') or [])} seeds = {want}")
    keys = [(r.get("item_id"), r.get("seed")) for r in rows]
    dups = sorted({k for k in keys if keys.count(k) > 1}, key=str)
    if dups:
        problems.append(f"duplicated (item, seed) rows: {dups[:5]}")
    bkeys = {(r.get("item_id"), r.get("seed")) for r in brows}
    if set(keys) != bkeys:
        miss, extra = sorted(bkeys - set(keys), key=str), sorted(set(keys) - bkeys, key=str)
        problems.append(f"(item, seed) set differs from baseline: missing {miss[:5]}{'…' if len(miss) > 5 else ''}"
                        f" extra {extra[:5]}{'…' if len(extra) > 5 else ''}")
    bman = base.get("manifest") or {}
    for k in ("items", "seeds"):
        if k in bman and man.get(k) != bman.get(k):
            problems.append(f"manifest {k} {man.get(k)} != baseline {bman.get(k)}")

    for r in rows:
        bad = [m for m in graded if r.get(m) is None]
        if bad:
            problems.append(f"row {r.get('item_id')}@{r.get('seed')} has no value for graded metric(s) {bad}")
            break

    # slice tags: consistent across seeds and identical to the baseline's
    def tags(rs):
        out: dict[str, set] = {}
        for r in rs:
            out.setdefault(r.get("item_id"), set()).add(tuple(sorted(r.get("slices") or [])))
        return out
    pt, bt = tags(rows), tags(brows)
    for item, t in sorted(pt.items(), key=str):
        if len(t) > 1:
            problems.append(f"item {item} carries different slice tags across seeds: {sorted(t)}")
        elif item in bt and t != bt[item]:
            problems.append(f"item {item} slice tags {sorted(t)} != baseline {sorted(bt[item])}")

    # the summary must be what the rows say (no hand-edited metrics)
    problems += _metrics_match_rows(pr, spec)

    if base_spec is not None:
        problems += _ratchet(spec, base_spec)
    return problems


def _metrics_match_rows(rep: dict, spec: dict) -> list[str]:
    from lab9.eval import aggregate
    from lab9.graders import GRADERS

    rows = rep.get("rows") or []
    if not rows:
        return []
    ids = [m for m in GRADERS if m in (rep.get("metrics") or {}) and all(m in r for r in rows)]
    if any(r.get(m) is None for r in rows for m in ids):
        return []                                  # already reported as a missing value
    has_cost = all("cost" in r for r in rows)
    try:
        again = aggregate([r if has_cost else {**r, "cost": 0.0} for r in rows], ids,
                          k_values=spec.get("pass_k", []))
    except Exception as e:                         # noqa: BLE001 - malformed rows are a problem too
        return [f"cannot recompute metrics from rows: {e!r}"]
    out = []
    for k, v in again.items():
        if k not in rep["metrics"] or (k == "cost_per_success" and not has_cost):
            continue
        got = rep["metrics"][k]
        if v is None and got is None:
            continue
        if v is None or not isinstance(got, (int, float)) or abs(float(got) - float(v)) > 1e-3:
            out.append(f"metric {k} = {got} but rows give {v}")
    return out


def _thresholds_looser(what: str, new: dict, old: dict) -> list[str]:
    out = []
    nt, ot = new.get("threshold", new) or {}, old.get("threshold", old) or {}
    if "min" in ot and ("min" not in nt or nt["min"] < ot["min"]):
        out.append(f"{what}: min {ot['min']} -> {nt.get('min')}")
    for k in ("max", "max_increase"):
        if k in ot and (k not in nt or nt[k] > ot[k]):
            out.append(f"{what}: {k} {ot[k]} -> {nt.get(k)}")
    if ot.get("no_significant_drop") and not nt.get("no_significant_drop"):
        out.append(f"{what}: no_significant_drop dropped")
    if old.get("blocking", "slice" in what) and not new.get("blocking", "slice" in what):
        out.append(f"{what}: blocking -> non-blocking")
    return out


def _ratchet(spec: dict, base_spec: dict) -> list[str]:
    """Thresholds may only get stricter. Applied whenever a base spec is given: the gate already
    requires the same eval_set_sha, so a renamed eval_set_version is not a licence to loosen."""
    out = []
    new_m = {m["id"]: m for m in spec.get("metrics", [])}
    for m in base_spec.get("metrics", []):
        if m["id"] not in new_m:
            out.append(f"ratchet: metric {m['id']} removed")
        else:
            out += [f"ratchet: {p}" for p in _thresholds_looser(f"metric {m['id']}", new_m[m["id"]], m)]
    new_s = {(s["name"], s.get("metric", "pass_rate")): s for s in spec.get("slices") or []}
    for s in base_spec.get("slices") or []:
        key = (s["name"], s.get("metric", "pass_rate"))
        if key not in new_s:
            out.append(f"ratchet: slice {key[0]}/{key[1]} removed")
        else:
            out += [f"ratchet: {p}" for p in _thresholds_looser(f"slice {key[0]}/{key[1]}", new_s[key], s)]
    if (spec.get("bootstrap") or {}) != (base_spec.get("bootstrap") or {}):
        out.append(f"ratchet: bootstrap settings changed {base_spec.get('bootstrap')} -> {spec.get('bootstrap')}")
    if spec.get("eval_set_version") != base_spec.get("eval_set_version"):
        out.append(f"ratchet: eval_set_version renamed {base_spec.get('eval_set_version')} -> "
                   f"{spec.get('eval_set_version')} on the same eval set")
    return out


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices") or []:
        name, metric = s["name"], s.get("metric", "pass_rate")
        sid = f"slice:{name}/{metric}"
        a, b = per_item(pr, metric, slice_name=name), per_item(base, metric, slice_name=name)
        verdict, note, val = "ok", "", None
        if not a:
            verdict, note = "fail", "empty slice"
        else:
            val = round(sum(a.values()) / len(a), 4)
            if "min" in s and val < s["min"]:
                verdict = "fail"
            if "max" in s and val > s["max"]:
                verdict = "fail"
            if s.get("no_significant_drop"):
                keys = sorted(set(a) & set(b))
                if keys:
                    d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                       n_resamples=bs.get("n_resamples", 1000),
                                                       rng=bs.get("rng", 2027),
                                                       confidence=bs.get("confidence", 0.95))
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}] n={len(keys)}"
                    if hi < 0:
                        verdict = "fail"
                else:
                    verdict, note = "fail", "no items shared with baseline"
        is_blocking = s.get("blocking", True)
        if verdict != "ok" and is_blocking:
            blocked.append(sid)
        label = "ok" if verdict == "ok" else ("BLOCK" if is_blocking else "warn")
        th = {k: s[k] for k in ("min", "max", "no_significant_drop") if k in s}
        lines.append(f"  {sid:<34} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
