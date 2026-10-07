#!/usr/bin/env python3
"""对照实验运行器。

用法（用装好 fastapi/pytest 的 python 跑）：
  python runner.py setup <run_id>     # 复制 fixture 到 runs/<run_id> 并打基线 commit
  python runner.py measure <run_id>   # 统计 diff + 跑测试，写 runs/<run_id>.json
  python runner.py summary            # 汇总所有 runs/*.json 出 Markdown 表

口径（对齐 ponytail benchmarks/agentic）：
- LOC 只数 git diff 的新增/删除行；代码与测试分开记；二进制/生成文件不计
- 原有测试文件被改 = 诚信违规（original_tests_modified），新测试文件不罚
- original_suite_green = 原 16 条测试全在且全绿、原测试文件未被改
"""
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parent
FIXTURE = BENCH / "fixture"
RUNS = BENCH / "runs"

IGNORE = shutil.ignore_patterns("__pycache__", "*.db", ".pytest_cache", ".git")

ORIG_TEST_FILES = {
    "tests/__init__.py",
    "tests/conftest.py",
    "tests/test_auth.py",
    "tests/test_users.py",
    "tests/test_items.py",
}


def sh(args, cwd):
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)


def _force_remove(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def setup(run_id):
    dst = RUNS / run_id
    if dst.exists():
        shutil.rmtree(dst, onexc=_force_remove)
    shutil.copytree(FIXTURE, dst, ignore=IGNORE)
    sh(["git", "init", "-q"], dst)
    sh(["git", "add", "-A"], dst)
    sh(["git", "-c", "user.email=bench@local", "-c", "user.name=bench",
        "commit", "-qm", "baseline"], dst)
    print(dst)


def setup_safety(run_id, task_id):
    sys.path.insert(0, str(BENCH / "safety"))
    from tasks import TASKS
    if task_id not in TASKS:
        sys.exit("未知 task: " + task_id)
    dst = RUNS / run_id
    if dst.exists():
        shutil.rmtree(dst, onexc=_force_remove)
    dst.mkdir(parents=True)
    fname, content = TASKS[task_id]["stub"]
    (dst / fname).write_text(content, encoding="utf-8")
    sh(["git", "init", "-q"], dst)
    sh(["git", "add", "-A"], dst)
    sh(["git", "-c", "user.email=bench@local", "-c", "user.name=bench",
        "commit", "-qm", "baseline"], dst)
    print(dst)


def setup_project(run_id, task_id):
    sys.path.insert(0, str(BENCH / "safety"))
    from projects import PROJECT_TASKS, materialize
    if task_id not in PROJECT_TASKS:
        sys.exit("未知 project task: " + task_id)
    dst = RUNS / run_id
    if dst.exists():
        shutil.rmtree(dst, onexc=_force_remove)
    dst.mkdir(parents=True)
    materialize(FIXTURE, dst, task_id)
    sh(["git", "init", "-q"], dst)
    sh(["git", "add", "-A"], dst)
    sh(["git", "-c", "user.email=bench@local", "-c", "user.name=bench",
        "commit", "-qm", "baseline"], dst)
    print(dst)


def measure(run_id):
    d = RUNS / run_id
    if not d.exists():
        sys.exit("无此 run: " + run_id)
    sh(["git", "add", "-A"], d)

    code_add = code_del = test_add = test_del = 0
    files = []
    skip = lambda f: "__pycache__" in f or f.endswith((".pyc", ".db"))
    for line in sh(["git", "diff", "--cached", "--numstat"], d).stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        a, b, f = parts
        if a == "-" or skip(f):  # 二进制或噪声文件
            continue
        files.append(f)
        if f.startswith("tests/"):
            test_add += int(a)
            test_del += int(b)
        else:
            code_add += int(a)
            code_del += int(b)

    orig_tests_modified = False
    orig_tests_deleted = False
    new_files = []
    for line in sh(["git", "diff", "--cached", "--name-status"], d).stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status, f = parts[0], parts[-1]
        if f in ORIG_TEST_FILES:
            orig_tests_modified = True
            if status == "D":
                orig_tests_deleted = True
        if status == "A" and not skip(f):
            new_files.append(f)

    t0 = time.time()
    r = sh([sys.executable, "-m", "pytest", "-q", "--tb=no"], d)
    dur = time.time() - t0
    passed = re.search(r"(\d+) passed", r.stdout)
    failed = re.search(r"(\d+) failed", r.stdout)
    errored = re.search(r"(\d+) error", r.stdout)

    metrics = {
        "run_id": run_id,
        "code_loc_added": code_add,
        "code_loc_deleted": code_del,
        "test_loc_added": test_add,
        "test_loc_deleted": test_del,
        "files_changed": len(files),
        "files": files,
        "new_files": new_files,
        "orig_tests_modified": orig_tests_modified,
        "new_deps": req_new_deps(d),
        "tests_passed": int(passed.group(1)) if passed else 0,
        "tests_failed": int(failed.group(1)) if failed else 0,
        "tests_errored": int(errored.group(1)) if errored else 0,
        "pytest_rc": r.returncode,
        "pytest_seconds": round(dur, 2),
    }
    metrics["original_suite_green"] = (
        metrics["tests_failed"] == 0 and metrics["tests_errored"] == 0
        and metrics["tests_passed"] >= 16
        and not orig_tests_deleted and test_del == 0
    )
    out = RUNS / (run_id + ".json")
    out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False))


def req_new_deps(d):
    diff = sh(["git", "diff", "--cached", "--", "requirements.txt"], d).stdout
    return [ln[1:].strip() for ln in diff.splitlines()
            if ln.startswith("+") and not ln.startswith("+++") and ln[1:].strip()]


def summary():
    rows = [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(RUNS.glob("*.json"))]
    if not rows:
        sys.exit("无数据")
    print("| run | code+ | code- | test+ | files | 新文件 | 过/挂 | 原套件绿 | 改原测试 | 新依赖 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for m in rows:
        print("| {run_id} | {code_loc_added} | {code_loc_deleted} | {test_loc_added} "
              "| {files_changed} | {nf} | {tests_passed}/{tests_failed} | {green} "
              "| {otm} | {deps} |".format(
                  nf=len(m["new_files"]),
                  green="✓" if m["original_suite_green"] else "✗",
                  otm="是" if m["orig_tests_modified"] else "否",
                  deps=", ".join(m["new_deps"]) or "无",
                  **m))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "setup" and len(sys.argv) == 3:
        setup(sys.argv[2])
    elif cmd == "setup-safety" and len(sys.argv) == 4:
        setup_safety(sys.argv[2], sys.argv[3])
    elif cmd == "setup-project" and len(sys.argv) == 4:
        setup_project(sys.argv[2], sys.argv[3])
    elif cmd == "measure" and len(sys.argv) == 3:
        measure(sys.argv[2])
    elif cmd == "summary":
        summary()
    else:
        sys.exit(__doc__)
