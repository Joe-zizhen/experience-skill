#!/usr/bin/env python3
"""状态机首版五命令的黑盒回归自测。"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "tools" / "workflow.py"
GENERATOR = ROOT / "tools" / "generate-workflow.py"
CONTRACT_FILES = ("suite-v1.yaml", "workflow.yaml", "workflow.json")


class TestFailure(Exception):
    pass


def fail(message):
    raise TestFailure(message)


def assert_true(condition, message):
    if not condition:
        fail(message)


def write_text(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(value)


def write_json(path, value):
    write_text(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def read_json(path):
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return json.load(handle)


def read_bytes(path):
    with Path(path).open("rb") as handle:
        return handle.read()


def write_bytes(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(value)


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def run_cli(root, *args):
    command = [sys.executable, "-X", "utf8", str(WORKFLOW), *args, "--root", str(root)]
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        fail("CLI 无 JSON 输出: %s\nstderr=%s" % (completed.args, completed.stderr))
    try:
        result = json.loads(lines[-1])
    except ValueError as exc:
        fail("CLI 输出不是 JSON: %s\nstdout=%s\nstderr=%s" % (exc, completed.stdout, completed.stderr))
    return completed.returncode, result


def run_generator(root, *args):
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", str(GENERATOR), "--root", str(root), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
    )
    return completed.returncode, completed.stdout, completed.stderr


def make_root(temp_root):
    root = Path(temp_root)
    contracts = root / "contracts"
    contracts.mkdir(parents=True, exist_ok=True)
    for name in CONTRACT_FILES:
        shutil.copyfile(ROOT / "contracts" / name, contracts / name)
    return root


def prepare_case(root, task_id="workflow-selftest"):
    evidence = root / "evidence.txt"
    write_text(evidence, "stable evidence\n")
    evidence_ref = {
        "kind": "test-run",
        "path": "evidence.txt",
        "sha256": sha256(read_bytes(evidence)),
        "exit_code": 0,
    }
    handoff = {
        "observed_behavior": "observed",
        "expected_behavior": "expected",
        "reproduction": "python reproduce.py",
        "evidence_refs": [evidence_ref],
        "confirmed_mechanism_or_hypothesis": "hypothesis",
        "confidence": "medium",
        "scope": "task",
        "unknowns": "none",
        "invariant": "invariant",
        "falsifier": "falsifier",
        "decision_owner": "owner",
        "minimal_reversible_action": "action",
    }
    handoff_path = root / "handoff.json"
    write_json(handoff_path, handoff)
    scope = {
        "task_id": task_id,
        "class": "multi-skill-chain",
        "initial_stage": "pm",
        "source": "user",
        "primary_skills": ["pm", "first-principle-v2"],
    }
    scope_path = root / "scope-input.json"
    write_json(scope_path, scope)
    return scope_path, handoff_path, handoff, evidence_ref


def assert_exit(actual, expected, label):
    if actual != expected:
        fail("%s: 退出码 %d != %d" % (label, actual, expected))


def test_not_in_scope():
    with tempfile.TemporaryDirectory(prefix="workflow-out-", dir=str(ROOT)) as temp:
        root = make_root(temp)
        scope_path, _, _, _ = prepare_case(root, "out-of-scope")
        scope = read_json(scope_path)
        scope["primary_skills"] = ["pm"]
        write_json(scope_path, scope)
        code, result = run_cli(root, "init", "--scope", str(scope_path))
        assert_exit(code, 2, "范围闸")
        assert_true(result["error"] == "not-in-scope", "范围闸错误码不稳定")
        assert_true(not (root / ".workflow").exists(), "范围闸失败后创建了状态目录")


def test_lifecycle():
    with tempfile.TemporaryDirectory(prefix="workflow-case-", dir=str(ROOT)) as temp:
        root = make_root(temp)
        scope_path, handoff_path, handoff, evidence_ref = prepare_case(root)

        code, result = run_cli(root, "init", "--scope", str(scope_path))
        assert_exit(code, 0, "init")
        assert_true(result["epoch"] == 0 and result["stage"] == "pm", "init 初始状态错误")
        code, result = run_cli(root, "status")
        assert_exit(code, 0, "status")
        assert_true(result["approved_current_epoch"] is False, "init 不应带批准")

        code, result = run_cli(root, "transition", "--epoch", "0", "--to", "first-principle-v2", "--handoff", str(handoff_path), "--actor-label", "")
        assert_exit(code, 1, "空 transition actor")
        assert_true(result["error"] == "transition-invalid", "空 transition actor 未被拒绝")
        code, result = run_cli(root, "approve", "--epoch", "0", "--actor-label", "", "--reason", "无效身份")
        assert_exit(code, 1, "空 approve actor")
        assert_true(result["error"] == "approval-invalid", "空 approve actor 未被拒绝")
        code, result = run_cli(root, "approve", "--epoch", "0", "--actor-label", "operator", "--reason", "")
        assert_exit(code, 1, "空 approve reason")
        assert_true(result["error"] == "approval-invalid", "空 approve reason 未被拒绝")

        code, result = run_cli(root, "transition", "--epoch", "0", "--to", "senior-engineer", "--handoff", str(handoff_path))
        assert_exit(code, 1, "未批准执行门")
        assert_true(result["error"] == "approval-required", "未批准执行门错误码不稳定")

        missing = dict(handoff)
        missing.pop("falsifier")
        missing_path = root / "handoff-missing.json"
        write_json(missing_path, missing)
        code, result = run_cli(root, "transition", "--epoch", "0", "--to", "first-principle-v2", "--handoff", str(missing_path))
        assert_exit(code, 1, "缺 handoff 字段")
        assert_true(result["error"] == "handoff-invalid", "缺 handoff 字段错误码不稳定")

        bad_evidence = dict(handoff)
        bad_evidence["evidence_refs"] = [dict(evidence_ref, sha256="0" * 64)]
        bad_evidence_path = root / "handoff-bad-evidence.json"
        write_json(bad_evidence_path, bad_evidence)
        code, result = run_cli(root, "transition", "--epoch", "0", "--to", "first-principle-v2", "--handoff", str(bad_evidence_path))
        assert_exit(code, 1, "坏证据")
        assert_true(result["error"] == "evidence-invalid", "坏证据错误码不稳定")

        traversal = dict(handoff)
        traversal["evidence_refs"] = [dict(evidence_ref, path="../outside-evidence.txt", sha256="0" * 64)]
        traversal_path = root / "handoff-traversal.json"
        write_json(traversal_path, traversal)
        code, result = run_cli(root, "transition", "--epoch", "0", "--to", "first-principle-v2", "--handoff", str(traversal_path))
        assert_exit(code, 1, "证据路径越界")
        assert_true(result["error"] == "evidence-invalid", "证据路径越界错误码不稳定")

        code, result = run_cli(root, "transition", "--epoch", "0", "--to", "first-principle-v2", "--handoff", str(handoff_path))
        assert_exit(code, 0, "合法交接")
        assert_true(result["epoch"] == 0 and result["stage"] == "first-principle-v2", "合法交接状态错误")

        code, result = run_cli(root, "transition", "--epoch", "1", "--to", "systematic-debugging", "--handoff", str(handoff_path))
        assert_exit(code, 3, "旧 epoch")
        assert_true(result["error"] == "stale-epoch", "旧 epoch 错误码不稳定")

        code, result = run_cli(root, "approve", "--epoch", "0", "--actor-label", "agent-or-human-unknown", "--reason", "批准进入实现")
        assert_exit(code, 0, "approve")
        assert_true(result["epoch"] == 1 and result["identity_verified"] is False, "approve epoch 或身份字段错误")
        events = [json.loads(line) for line in read_bytes(root / ".workflow" / "events.jsonl").decode("utf-8").splitlines()]
        assert_true(events[-1]["event"] == "approve" and events[-1]["identity_verified"] is False, "approve 事件未记录身份诚实字段")

        code, result = run_cli(root, "transition", "--epoch", "1", "--to", "senior-engineer", "--handoff", str(handoff_path))
        assert_exit(code, 0, "批准后执行")
        assert_true(result["stage"] == "senior-engineer", "批准后执行阶段错误")
        code, result = run_cli(root, "transition", "--epoch", "1", "--to", "pm", "--handoff", str(handoff_path))
        assert_exit(code, 0, "回流")
        assert_true(result["stage"] == "pm", "回流阶段错误")
        code, result = run_cli(root, "check")
        assert_exit(code, 0, "check")
        assert_true(result["event_count"] == 5, "check event_count 错误")

        code, result = run_cli(root, "approve", "--recover", "--epoch", "1", "--actor-label", "operator", "--reason", "健康状态不应恢复")
        assert_exit(code, 1, "健康 recover")
        assert_true(result["error"] == "recovery-not-needed", "健康 recover 未被拒绝")
        code, result = run_cli(root, "approve", "--recover", "--epoch", "99", "--actor-label", "operator", "--reason", "旧 epoch")
        assert_exit(code, 3, "recover 旧 epoch")

        events_path = root / ".workflow" / "events.jsonl"
        write_bytes(events_path, read_bytes(events_path) + b"\n")
        code, result = run_cli(root, "check")
        assert_exit(code, 1, "损坏日志 check")
        assert_true(result["error"] == "state-corrupt", "损坏日志未失败关闭")
        code, result = run_cli(root, "approve", "--recover", "--epoch", "1", "--actor-label", "operator", "--reason", "归档损坏日志并恢复")
        assert_exit(code, 0, "recover")
        assert_true(result["epoch"] == 3 and result["identity_verified"] is False, "recover epoch 或身份字段错误")
        archive_files = list((root / ".workflow" / "archive").glob("*.jsonl"))
        assert_true(len(archive_files) == 1, "recover 未产生唯一归档")
        code, result = run_cli(root, "check")
        assert_exit(code, 0, "recover 后 check")
        assert_true(result["epoch"] == 3 and result["approved_current_epoch"] is True, "recover 后状态错误")

        # 构造一个未完成事务，验证 approve --recover 能从事务事实续接，而不是编辑日志。
        manifest = read_json(root / ".workflow" / "manifest.json")
        old_raw = read_bytes(events_path)
        contract_hash = manifest["contract_hash"]
        recovery = {
            "actor_label": "operator",
            "archived_events_sha256": sha256(old_raw),
            "contract_hash": contract_hash,
            "epoch": 4,
            "event": "recovery",
            "evidence_refs": [],
            "handoff": {},
            "identity_verified": False,
            "reason": "续接事务",
            "recovered_from_epoch": 3,
            "stage": manifest["stage"],
            "task_id": manifest["task_id"],
            "timestamp": "2026-01-01T00:00:00Z",
        }
        approval = {
            "actor_label": "operator",
            "approved_stage": manifest["stage"],
            "contract_hash": contract_hash,
            "epoch": 5,
            "event": "approve",
            "evidence_refs": [],
            "handoff": {},
            "identity_verified": False,
            "reason": "续接事务",
            "recovery_from_epoch": 4,
            "stage": manifest["stage"],
            "task_id": manifest["task_id"],
            "timestamp": "2026-01-01T00:00:01Z",
        }
        new_raw = (json.dumps(recovery, ensure_ascii=False, sort_keys=True) + "\n" + json.dumps(approval, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        txn = {
            "archive_rel": "archive/resume.jsonl",
            "new_rel": "recovery.new.jsonl",
            "old_sha256": sha256(old_raw),
            "new_sha256": sha256(new_raw),
            "old_epoch": 3,
            "manifest": dict(manifest, epoch=5, events_sha256=sha256(new_raw)),
            "new_events": [recovery, approval],
        }
        write_json(root / ".workflow" / "recovery.txn.json", txn)
        code, result = run_cli(root, "approve", "--recover", "--epoch", "2", "--actor-label", "operator", "--reason", "错误 epoch")
        assert_exit(code, 3, "事务恢复旧 epoch")
        assert_true((root / ".workflow" / "recovery.txn.json").exists(), "旧 epoch 误消费恢复事务")
        code, result = run_cli(root, "approve", "--recover", "--epoch", "3", "--actor-label", "operator", "--reason", "续接事务")
        assert_exit(code, 0, "恢复事务续接")
        assert_true(result["epoch"] == 5, "恢复事务续接 epoch 错误")
        code, result = run_cli(root, "check")
        assert_exit(code, 0, "事务续接后 check")
        assert_true(result["epoch"] == 5, "事务续接后状态错误")


def test_contract_guards():
    with tempfile.TemporaryDirectory(prefix="workflow-contract-", dir=str(ROOT)) as temp:
        root = make_root(temp)
        code, _, _ = run_generator(root, "--check")
        assert_exit(code, 0, "临时契约初始检查")
        workflow_json = root / "contracts" / "workflow.json"
        write_bytes(workflow_json, read_bytes(workflow_json) + b" ")
        code, _, _ = run_generator(root, "--check")
        assert_exit(code, 1, "生成物篡改检查")
        scope_path, _, _, _ = prepare_case(root, "bad-contract")
        code, result = run_cli(root, "init", "--scope", str(scope_path))
        assert_exit(code, 1, "篡改生成物失败关闭")
        assert_true(result["error"] == "contract-invalid", "篡改生成物错误码不稳定")

        shutil.copyfile(ROOT / "contracts" / "workflow.json", workflow_json)
        suite_path = root / "contracts" / "suite-v1.yaml"
        suite_text = suite_path.read_text(encoding="utf-8")
        write_text(suite_path, suite_text.replace('"kind": "forward"', '"kind": "sideways"', 1))
        code, _, _ = run_generator(root, "--check")
        assert_exit(code, 1, "非法转换 kind 检查")
        shutil.copyfile(ROOT / "contracts" / "suite-v1.yaml", suite_path)
        write_bytes(root / "contracts" / "workflow.yaml", b"{not-json\n")
        code, _, _ = run_generator(root, "--check")
        assert_exit(code, 1, "坏源契约检查")

        shutil.copyfile(ROOT / "contracts" / "workflow.json", workflow_json)
        write_bytes(workflow_json, b"\xef\xbb\xbf" + read_bytes(workflow_json))
        code, _, _ = run_generator(root, "--check")
        assert_exit(code, 1, "BOM 生成物检查")


def test_scope_evidence_ref():
    with tempfile.TemporaryDirectory(prefix="workflow-scope-ev-", dir=str(ROOT)) as temp:
        root = make_root(temp)
        scope_path, _, _, _ = prepare_case(root, "scope-evidence")
        scope = read_json(scope_path)
        scope["evidence_refs"] = [{
            "kind": "test-run",
            "path": "missing.txt",
            "sha256": "0" * 64,
            "exit_code": 0,
        }]
        write_json(scope_path, scope)
        code, result = run_cli(root, "init", "--scope", str(scope_path))
        assert_exit(code, 1, "范围证据悬空")
        assert_true(result["error"] == "evidence-invalid", "范围证据悬空错误码不稳定")
        assert_true(not (root / ".workflow").exists(), "范围证据悬空后创建了状态目录")


def main():
    tests = [test_not_in_scope, test_scope_evidence_ref, test_lifecycle, test_contract_guards]
    try:
        for test in tests:
            test()
            print("PASS " + test.__name__)
    except (AssertionError, OSError, TestFailure, ValueError) as exc:
        print("FAIL " + str(exc))
        return 1
    print("WORKFLOW SELFTEST PASSED (%d cases)" % len(tests))
    return 0


if __name__ == "__main__":
    sys.exit(main())
