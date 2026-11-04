"""Sensitivity of the recorded results. Reads data/chaos.sqlite3 and changes nothing.

Run from the repository root:  python docs/sensitivity.py

The README's "How far to trust the results" section quotes this output.
"""
from __future__ import annotations

import json
import sqlite3
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from chaos import detection  # noqa: E402

db = sqlite3.connect(f"file:{ROOT / 'data' / 'chaos.sqlite3'}?mode=ro", uri=True)

# ---- resilience per (fault, target), oldest run first
runs: dict[tuple[str, str], list[dict]] = defaultdict(list)
for (data,) in db.execute("SELECT data FROM analyses ORDER BY created"):
    a = json.loads(data)
    if a["resilience"].get("score") is None or a["deterministic"].get("abort_kind") == "manual":
        continue
    d = a["deterministic"]
    runs[(d["fault_type"], d["target"])].append(a)

print("Scenario                      runs  resilience min/median/max  severity min/median/max")
for key, rs in sorted(runs.items()):
    res = [r["resilience"]["score"] for r in rs]
    sev = [r["severity"]["score"] for r in rs]
    print(f"{key[0] + ' ' + key[1]:<30}{len(rs):>3}   {min(res):5.1f} {st.median(res):5.1f} {max(res):5.1f}"
          f"          {min(sev):5.1f} {st.median(sev):5.1f} {max(sev):5.1f}")

mean = lambda xs: round(sum(xs) / len(xs), 1)  # noqa: E731
print("\nOverall score under different choices of run per scenario")
print("  latest run (what the product reports):", mean([rs[-1]["resilience"]["score"] for rs in runs.values()]))
print("  median run:", mean([st.median(r["resilience"]["score"] for r in rs) for rs in runs.values()]))
print("  best run:  ", mean([max(r["resilience"]["score"] for r in rs) for rs in runs.values()]))
print("  worst run: ", mean([min(r["resilience"]["score"] for r in rs) for rs in runs.values()]))

# ---- the same latest runs under other component weights
WEIGHTS = {"shipped 50/20/30": (.5, .2, .3), "equal": (1 / 3, 1 / 3, 1 / 3),
           "availability 70/15/15": (.7, .15, .15), "recovery 30/20/50": (.3, .2, .5)}
print("\nOverall score under other weights (availability/performance/recovery)")
for name, (w_a, w_p, w_r) in WEIGHTS.items():
    scores = []
    for rs in runs.values():
        c = rs[-1]["resilience"]["components"]
        parts = [(c.get("availability"), w_a), (c.get("performance"), w_p), (c.get("recovery"), w_r)]
        parts = [(v, w) for v, w in parts if v is not None]
        scores.append(100 * sum(v * w for v, w in parts) / sum(w for _, w in parts))
    print(f"  {name}: {mean(scores)}")

# ---- the self-healing agent, graded against what was really injected
total = defaultdict(lambda: [0, 0])
times = defaultdict(list)
outcomes: dict[str, int] = defaultdict(int)
for (data,) in db.execute("SELECT data FROM incidents ORDER BY created"):
    inc = json.loads(data)
    row = db.execute("SELECT config, fault_start FROM runs WHERE id = ?", (inc["run_id"],)).fetchone()
    cfg, fs = (json.loads(row[0] or "{}"), row[1]) if row else ({}, None)
    outcomes[inc.get("status")] += 1
    atts = inc.get("attempts") or []
    if not atts or not fs:
        continue
    expected = detection.expected_class(cfg.get("fault_type"), cfg.get("target"))
    mode = atts[0]["source"]["mode"]
    total[mode][0] += atts[-1]["diagnosis"]["failure_class"] == expected
    total[mode][1] += 1
    total["first attempt"][0] += atts[0]["diagnosis"]["failure_class"] == expected
    total["first attempt"][1] += 1
    if inc.get("detected_at"):
        times["detect"].append(inc["detected_at"] - fs)
    if inc.get("resolved_at"):
        times["verified"].append(inc["resolved_at"] - fs)

print("\nSelf-healing incidents:", dict(outcomes))
print("Correct final diagnosis by the source of the first attempt, and correct on the first attempt:")
for k, (ok, n) in sorted(total.items()):
    print(f"  {k}: {ok} of {n}")
for k, v in times.items():
    print(f"Seconds from injection to {k}: n={len(v)} median={st.median(v):.1f} min={min(v):.1f} max={max(v):.1f}")

# ---- recovery after the fault was removed, across every analysed run
recovery, unverified = [], 0
for (data,) in db.execute("SELECT data FROM analyses"):
    d = json.loads(data)["deterministic"]
    if d.get("recovery_verified") and d.get("recovery_time_s") is not None:
        recovery.append(d["recovery_time_s"])
    elif d.get("injected"):
        unverified += 1
print(f"\nRecovery after fault removal: n={len(recovery)} median={st.median(recovery):.1f}s "
      f"max={max(recovery):.1f}s; injected runs without verified recovery: {unverified}")
