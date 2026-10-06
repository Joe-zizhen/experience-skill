#!/usr/bin/env python3
"""safety 打分器。

  python safety/scorer.py --selftest           # 验证 good 全 safe、bad 全被抓
  python safety/scorer.py <run_dir> <task_id>  # 给某个 run 打分，写 runs/<run_id>.json
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tasks import TASKS


def load_mod(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def score_source(source, task_id):
    task = TASKS[task_id]
    fname = task["stub"][0]
    d = tempfile.mkdtemp()
    p = Path(d) / fname
    p.write_text(source, encoding="utf-8")
    mod = load_mod(str(p), "candidate_" + task_id.replace("-", "_"))
    return task["score"](mod)


def selftest():
    ok = True
    for tid, task in TASKS.items():
        safe_good, f_good = score_source(task["good"], tid)
        safe_bad, f_bad = score_source(task["bad"], tid)
        line = "%s: good=%s bad=%s" % (tid,
                                       "safe" if safe_good else "UNSAFE!",
                                       "caught" if not safe_bad else "MISSED!")
        print(line)
        if not safe_good or safe_bad:
            ok = False
            print("  good failures:", f_good)
            print("  bad failures:", f_bad)
    print("SELFTEST " + ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1


def score_run(run_dir, task_id):
    task = TASKS[task_id]
    fname = task["stub"][0]
    p = Path(run_dir) / fname
    if not p.exists():
        sys.exit("缺文件: " + str(p))
    src = p.read_text(encoding="utf-8")
    if "NotImplementedError" in src:
        safe, failures = False, ["function left unimplemented"]
    else:
        safe, failures = score_source(src, task_id)
    out = {"run_id": Path(run_dir).name, "task_id": task_id,
           "axis": "safety", "safe": safe, "failures": failures}
    dest = BENCH / "runs" / (Path(run_dir).name + ".json")
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        sys.exit(selftest())
    if len(sys.argv) == 3:
        score_run(sys.argv[1], sys.argv[2])
    else:
        sys.exit(__doc__)
