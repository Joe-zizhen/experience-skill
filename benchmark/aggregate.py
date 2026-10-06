#!/usr/bin/env python3
"""聚合 runs/*.json：LOC 轴按 (ticket, arm) 出均值±标准差，safety 轴出 safe 率。

run_id 约定：LOC = tNN-<arm>（r1）或 tNN-<arm>-rK；safety = sN-xxx-<arm>-rK。
"""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

RUNS = Path(__file__).resolve().parent / "runs"


def split_id(run_id):
    parts = run_id.split("-")
    if parts[-1].startswith("r") and parts[-1][1:].isdigit():
        parts = parts[:-1]
    arm = parts[-1]
    ticket = "-".join(parts[:-1])
    return ticket, arm


def main():
    loc = defaultdict(list)
    green = defaultdict(list)
    tests = defaultdict(list)
    safe = defaultdict(list)
    fail_detail = defaultdict(list)
    for p in sorted(RUNS.glob("*.json")):
        m = json.loads(p.read_text(encoding="utf-8"))
        ticket, arm = split_id(m["run_id"])
        if m.get("axis") == "safety":
            safe[(ticket, arm)].append(m["safe"])
            for f in m.get("failures", []):
                fail_detail[(ticket, arm)].append(m["run_id"] + ": " + f)
        else:
            loc[(ticket, arm)].append(m["code_loc_added"])
            green[(ticket, arm)].append(m["original_suite_green"])
            tests[(ticket, arm)].append(m["test_loc_added"])

    arms = ["base", "yagni", "skill"]
    tickets = sorted({t for t, _ in loc})
    print("## LOC 轴：code_loc_added 均值 ± sd（n=%d 每格）" %
          max(len(v) for v in loc.values()))
    print("| ticket | " + " | ".join(arms) + " |")
    print("|---|" + "---|" * len(arms))
    totals = defaultdict(list)
    for t in tickets:
        row = ["| " + t]
        for a in arms:
            v = loc.get((t, a), [])
            totals[a].extend(v)
            row.append(("%d±%d" % (statistics.mean(v), statistics.stdev(v)))
                       if len(v) > 1 else (str(v[0]) if v else "-"))
        print(" | ".join(row) + " |")
    row = ["| **合计/均值**"]
    for a in arms:
        v = totals[a]
        row.append("**%d / %.1f±%.1f**" % (sum(v), statistics.mean(v),
                                           statistics.stdev(v)))
    print(" | ".join(row) + " |")

    print("\n## 测试 LOC 均值")
    for a in arms:
        vals = [statistics.mean(tests[(t, a)]) for t in tickets]
        print("- %s: %.1f" % (a, statistics.mean(vals)))

    print("\n## 原套件绿（比率）")
    for a in arms:
        vals = [g for t in tickets for g in green.get((t, a), [])]
        print("- %s: %d/%d" % (a, sum(vals), len(vals)))

    print("\n## safety 轴：safe 率")
    st = sorted({t for t, _ in safe})
    print("| task | " + " | ".join(arms) + " |")
    print("|---|" + "---|" * len(arms))
    arm_tot = defaultdict(lambda: [0, 0])
    for t in st:
        row = ["| " + t]
        for a in arms:
            v = safe.get((t, a), [])
            arm_tot[a][0] += sum(v)
            arm_tot[a][1] += len(v)
            row.append("%d/%d" % (sum(v), len(v)) if v else "-")
        print(" | ".join(row) + " |")
    row = ["| **合计**"]
    for a in arms:
        n, d = arm_tot[a]
        row.append("**%d/%d = %d%%**" % (n, d, 100 * n // d) if d else "-")
    print(" | ".join(row) + " |")
    if fail_detail:
        print("\n## 被抓的不安全样本")
        for k in sorted(fail_detail):
            for line in fail_detail[k]:
                print("- [%s] %s" % (k[1], line))


if __name__ == "__main__":
    sys.exit(main())
