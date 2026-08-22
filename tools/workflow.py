#!/usr/bin/env python3
"""跨阶段 workflow 状态机首版五命令。"""
import argparse
import datetime
import json
import os
import shutil
import sys
import time

from workflow_contract import ContractError, canonical_json, load_generated, sha256_bytes, sha256_file, write_bytes_atomic


class WorkflowError(Exception):
    def __init__(self, code, message, exit_code=1):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def emit(value):
    sys.stdout.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def state_path(root, name):
    return os.path.join(root, ".workflow", name)


def read_utf8(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
        if data.startswith(b"\xef\xbb\xbf"):
            raise WorkflowError("encoding-invalid", "文件含 UTF-8 BOM")
        text = data.decode("utf-8")
        if "\ufffd" in text:
            raise WorkflowError("encoding-invalid", "文件含替换字符 U+FFFD")
        return text
    except WorkflowError:
        raise
    except (OSError, UnicodeError) as exc:
        raise WorkflowError("file-unreadable", str(exc))


def read_json(path):
    try:
        return json.loads(read_utf8(path))
    except WorkflowError:
        raise
    except ValueError as exc:
        raise WorkflowError("json-invalid", "%s: %s" % (path, exc))


def write_json_atomic(path, value):
    write_bytes_atomic(path, canonical_json(value))


def load_contract(root):
    try:
        return load_generated(root)
    except (ContractError, OSError, ValueError, KeyError, TypeError) as exc:
        raise WorkflowError("contract-invalid", str(exc))


def contract_hash(root):
    return sha256_file(os.path.join(root, "contracts", "workflow.json"))


def relative_file(root, value):
    if not isinstance(value, str) or not value or os.path.isabs(value):
        return None
    candidate = os.path.realpath(os.path.join(root, value))
    root_abs = os.path.realpath(root)
    try:
        if os.path.commonpath([root_abs, candidate]) != root_abs:
            return None
    except ValueError:
        return None
    return candidate


def validate_evidence_refs(root, refs):
    if not isinstance(refs, list):
        raise WorkflowError("evidence-invalid", "evidence_refs 必须是列表")
    for ref in refs:
        if not isinstance(ref, dict):
            raise WorkflowError("evidence-invalid", "evidence_refs 项必须是对象")
        required = {"kind", "path", "sha256", "exit_code"}
        if not required.issubset(ref):
            raise WorkflowError("evidence-invalid", "evidence_refs 项缺字段")
        if set(ref) - {"kind", "path", "sha256", "exit_code"}:
            raise WorkflowError("evidence-invalid", "evidence_refs 含未知字段")
        if not isinstance(ref["kind"], str) or not ref["kind"]:
            raise WorkflowError("evidence-invalid", "证据 kind 必须是非空字符串")
        path = relative_file(root, ref.get("path"))
        if path is None or not os.path.isfile(path):
            raise WorkflowError("evidence-invalid", "证据路径必须是任务根目录内的已有文件")
        digest = ref.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise WorkflowError("evidence-invalid", "证据 sha256 格式错误")
        if sha256_file(path) != digest:
            raise WorkflowError("evidence-invalid", "证据 sha256 不匹配: " + ref["path"])
        if not isinstance(ref.get("exit_code"), int) or isinstance(ref.get("exit_code"), bool):
            raise WorkflowError("evidence-invalid", "证据 exit_code 必须是整数")


def validate_scope(root, scope, contract):
    required = {"task_id", "class", "initial_stage", "source"}
    if not isinstance(scope, dict) or not required.issubset(scope):
        raise WorkflowError("not-in-scope", "scope 缺少范围判定字段", 2)
    stages = contract["stages"]["primary"]
    execution = contract["stages"]["execution"]
    if not isinstance(scope["task_id"], str) or not scope["task_id"]:
        raise WorkflowError("not-in-scope", "task_id 不能为空", 2)
    if not isinstance(scope["initial_stage"], str) or scope["initial_stage"] not in stages or scope["initial_stage"] in execution:
        raise WorkflowError("not-in-scope", "initial_stage 非法或绕过执行批准门", 2)
    if not isinstance(scope["source"], str) or scope["source"] not in {"user", "task-book", "incident-record"}:
        raise WorkflowError("not-in-scope", "scope source 非法", 2)
    classes = contract["scope"]["classes"]
    scope_class = scope["class"]
    if not isinstance(scope_class, str):
        raise WorkflowError("not-in-scope", "范围类别非法", 2)
    if scope_class not in classes:
        raise WorkflowError("not-in-scope", "未知范围类别", 2)
    if scope_class == "multi-skill-chain":
        skills = scope.get("primary_skills")
        if not isinstance(skills, list) or len(skills) < classes[scope_class]["min_primary_skills"]:
            raise WorkflowError("not-in-scope", "主 skill 数不足", 2)
        if any(not isinstance(skill, str) or not skill for skill in skills):
            raise WorkflowError("not-in-scope", "主 skill 名称非法", 2)
        if len(set(skills)) != len(skills):
            raise WorkflowError("not-in-scope", "主 skill 不得重复", 2)
        if any(skill not in stages for skill in skills):
            raise WorkflowError("not-in-scope", "主 skill 含未知名称", 2)
    elif scope_class == "task-book-delivery":
        for field in classes[scope_class]["required_fields"]:
            if field not in scope:
                raise WorkflowError("not-in-scope", "任务书范围缺少 " + field, 2)
        if not isinstance(scope["handoff_fields"], list) or not scope["handoff_fields"]:
            raise WorkflowError("not-in-scope", "任务书 handoff_fields 不能为空", 2)
        contract_fields = set(contract["handoff"]["fields"])
        if any(not isinstance(field, str) or not field or field not in contract_fields for field in scope["handoff_fields"]):
            raise WorkflowError("not-in-scope", "任务书 handoff_fields 含未知字段", 2)
        if not isinstance(scope["acceptance_items"], list) or not scope["acceptance_items"]:
            raise WorkflowError("not-in-scope", "任务书 acceptance_items 不能为空", 2)
        task_book = relative_file(root, scope["task_book_ref"])
        if task_book is None or not os.path.isfile(task_book):
            raise WorkflowError("not-in-scope", "task_book_ref 必须指向任务根目录内文件", 2)
    else:
        refs = scope.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            raise WorkflowError("not-in-scope", "事故范围缺少可观察证据", 2)
        allowed = set(classes[scope_class]["evidence_kinds"])
        kinds = {ref.get("kind") for ref in refs if isinstance(ref, dict)}
        if not kinds.intersection(allowed):
            raise WorkflowError("not-in-scope", "事故范围缺少可观察条件", 2)
        validate_evidence_refs(root, refs)


def load_scope(root, contract):
    scope_path = state_path(root, "scope.json")
    scope = read_json(scope_path)
    validate_scope(root, scope, contract)
    return scope, sha256_file(scope_path)


def event_base(task_id, epoch, stage, event_type, actor, contract_digest, handoff=None, evidence_refs=None):
    return {
        "task_id": task_id,
        "epoch": epoch,
        "stage": stage,
        "event": event_type,
        "actor_label": actor,
        "timestamp": utc_now(),
        "contract_hash": contract_digest,
        "handoff": {} if handoff is None else handoff,
        "evidence_refs": [] if evidence_refs is None else evidence_refs,
    }


def write_events_atomic(path, events):
    raw = "".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events).encode("utf-8")
    write_bytes_atomic(path, raw)
    return raw


def read_event_bytes(path):
    try:
        with open(path, "rb") as f:
            raw = f.read()
        if raw.startswith(b"\xef\xbb\xbf") or b"\xef\xbf\xbd" in raw:
            raise WorkflowError("state-corrupt", "events.jsonl 编码损坏")
        raw.decode("utf-8")
        return raw
    except WorkflowError:
        raise
    except (OSError, UnicodeError) as exc:
        raise WorkflowError("state-corrupt", str(exc))


def parse_events(root, contract, raw, expected_contract_hash, check_files=True):
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise WorkflowError("state-corrupt", str(exc))
    if not lines or any(not line.strip() for line in lines):
        raise WorkflowError("state-corrupt", "events.jsonl 含空行或为空")
    events = []
    required = set(contract["event"]["required_fields"])
    allowed_types = set(contract["event"]["allowed_types"])
    stages = set(contract["stages"]["primary"])
    transitions = {(x["from"], x["to"]): x for x in contract["transitions"]}
    execution = set(contract["stages"]["execution"])
    current_epoch = None
    current_stage = None
    task_id = None
    approved_epochs = set()
    for index, line in enumerate(lines, 1):
        try:
            event = json.loads(line)
        except ValueError as exc:
            raise WorkflowError("state-corrupt", "第 %d 行不是 JSON: %s" % (index, exc))
        if not isinstance(event, dict) or not required.issubset(event):
            raise WorkflowError("state-corrupt", "第 %d 行缺事件字段" % index)
        if not isinstance(event.get("event"), str) or event["event"] not in allowed_types:
            raise WorkflowError("state-corrupt", "第 %d 行事件类型非法" % index)
        if task_id is None:
            task_id = event.get("task_id")
        elif event.get("task_id") != task_id:
            raise WorkflowError("state-corrupt", "第 %d 行 task_id 与日志不一致" % index)
        if not isinstance(task_id, str) or not task_id:
            raise WorkflowError("state-corrupt", "第 %d 行 task_id 非法" % index)
        if event["contract_hash"] != expected_contract_hash:
            raise WorkflowError("state-corrupt", "第 %d 行 contract_hash 与 manifest 不一致" % index)
        if not isinstance(event["stage"], str) or event["stage"] not in stages or not isinstance(event["epoch"], int) or isinstance(event["epoch"], bool) or event["epoch"] < 0:
            raise WorkflowError("state-corrupt", "第 %d 行 stage/epoch 非法" % index)
        if not isinstance(event["actor_label"], str) or not event["actor_label"]:
            raise WorkflowError("state-corrupt", "第 %d 行 actor_label 非法" % index)
        if not isinstance(event["timestamp"], str) or not event["timestamp"]:
            raise WorkflowError("state-corrupt", "第 %d 行 timestamp 非法" % index)
        if not isinstance(event["handoff"], dict) or not isinstance(event["evidence_refs"], list):
            raise WorkflowError("state-corrupt", "第 %d 行 handoff/evidence_refs 非法" % index)
        if check_files:
            validate_evidence_refs(root, event["evidence_refs"])
        if index == 1:
            if event["event"] == "init" and event["epoch"] == 0:
                current_epoch = 0
                if event["actor_label"] != "system":
                    raise WorkflowError("state-corrupt", "init actor_label 必须是 system")
            elif event["event"] == "recovery" and event["epoch"] >= 1:
                if event.get("identity_verified") is not False or not isinstance(event.get("reason"), str) or not event["reason"].strip():
                    raise WorkflowError("state-corrupt", "恢复首事件缺理由或身份诚实字段")
                if event.get("recovered_from_epoch") != event["epoch"] - 1:
                    raise WorkflowError("state-corrupt", "恢复 epoch 不连续")
                current_epoch = event["epoch"]
            else:
                raise WorkflowError("state-corrupt", "首事件必须是 epoch 0 的 init 或恢复事件")
            current_stage = event["stage"]
        elif event["event"] == "recovery":
            raise WorkflowError("state-corrupt", "recovery 只能作为日志首事件")
        elif event["event"] == "approve":
            if event["epoch"] != current_epoch + 1 or event["stage"] != current_stage:
                raise WorkflowError("state-corrupt", "第 %d 行 approve epoch 或 stage 不连续" % index)
            if event.get("identity_verified") is not False or not isinstance(event.get("reason"), str) or not event["reason"].strip():
                raise WorkflowError("state-corrupt", "approve 缺少身份诚实字段或理由")
            current_epoch = event["epoch"]
            approved_epochs.add(current_epoch)
        elif event["event"] == "transition":
            if event["epoch"] != current_epoch:
                raise WorkflowError("state-corrupt", "transition 不得改变 epoch")
            target = event["stage"]
            if event.get("from_stage") != current_stage or event.get("to_stage") != target:
                raise WorkflowError("state-corrupt", "第 %d 行 transition 起点/终点不一致" % index)
            edge = (current_stage, target)
            if edge not in transitions:
                raise WorkflowError("state-corrupt", "非法转换: %s -> %s" % edge)
            if target in execution and current_epoch not in approved_epochs:
                raise WorkflowError("state-corrupt", "进入执行阶段前缺 approve")
            fields = set(contract["handoff"]["fields"])
            if not fields.issubset(event["handoff"]):
                raise WorkflowError("state-corrupt", "transition 缺 handoff 字段")
            if set(event["handoff"]) - fields:
                raise WorkflowError("state-corrupt", "transition 含未知 handoff 字段")
            if event["handoff"].get("evidence_refs") != event["evidence_refs"]:
                raise WorkflowError("state-corrupt", "transition evidence_refs 与 handoff 不一致")
            current_stage = target
        elif event["event"] in {"contract_changed", "scope_changed"}:
            if event["epoch"] != current_epoch + 1 or event["stage"] != current_stage:
                raise WorkflowError("state-corrupt", "第 %d 行变更事件 epoch 或 stage 不连续" % index)
            if not isinstance(event.get("reason"), str) or not event["reason"].strip():
                raise WorkflowError("state-corrupt", "第 %d 行变更事件缺 reason" % index)
            current_epoch = event["epoch"]
        else:
            raise WorkflowError("state-corrupt", "未知状态事件")
        events.append(event)
    return events, current_epoch, current_stage, approved_epochs


def load_manifest(root):
    manifest = read_json(state_path(root, "manifest.json"))
    required = {"task_id", "epoch", "stage", "contract_hash", "scope_hash", "events_sha256"}
    if not isinstance(manifest, dict) or not required.issubset(manifest):
        raise WorkflowError("state-corrupt", "manifest 缺字段")
    if not isinstance(manifest["task_id"], str) or not manifest["task_id"]:
        raise WorkflowError("state-corrupt", "manifest task_id 非法")
    if not isinstance(manifest["epoch"], int) or isinstance(manifest["epoch"], bool) or manifest["epoch"] < 0:
        raise WorkflowError("state-corrupt", "manifest epoch 非法")
    for field in ("contract_hash", "scope_hash", "events_sha256"):
        value = manifest[field]
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise WorkflowError("state-corrupt", "manifest %s 非法" % field)
    return manifest


def load_state(root, allow_stale=False, check_files=True):
    workflow_dir = os.path.join(root, ".workflow")
    if not os.path.isdir(workflow_dir):
        raise WorkflowError("not-initialized", "任务尚未 init")
    if os.path.exists(state_path(root, "recovery.txn.json")):
        raise WorkflowError("recovery-pending", "存在未完成恢复事务")
    contract = load_contract(root)
    scope, scope_digest = load_scope(root, contract)
    manifest = load_manifest(root)
    raw = read_event_bytes(state_path(root, "events.jsonl"))
    events, epoch, stage, approved = parse_events(root, contract, raw, manifest["contract_hash"], check_files=check_files)
    if manifest["task_id"] != scope["task_id"] or manifest["epoch"] != epoch or manifest["stage"] != stage:
        raise WorkflowError("state-corrupt", "manifest 与事件重放结果不一致")
    if manifest["events_sha256"] != sha256_bytes(raw):
        raise WorkflowError("state-corrupt", "events.jsonl 哈希不一致")
    current_contract = contract_hash(root)
    blocked = []
    if manifest["contract_hash"] != current_contract:
        blocked.append("contract-hash-mismatch")
    if manifest["scope_hash"] != scope_digest:
        blocked.append("scope-hash-mismatch")
    if blocked and not allow_stale:
        raise WorkflowError("state-blocked", ",".join(blocked))
    return {
        "contract": contract,
        "scope": scope,
        "scope_hash": scope_digest,
        "contract_hash": current_contract,
        "events": events,
        "raw_events": raw,
        "manifest": manifest,
        "epoch": epoch,
        "stage": stage,
        "approved": epoch in approved,
        "blocked": blocked,
    }


class WorkflowLock:
    def __init__(self, root):
        self.path = state_path(root, "writer.lock")

    def __enter__(self):
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write("pid=%s\n" % os.getpid())
        except FileExistsError:
            raise WorkflowError("state-busy", "已有另一个状态写入者")
        except OSError as exc:
            raise WorkflowError("state-lock-failed", str(exc))
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass


def validate_handoff(root, handoff, contract):
    if not isinstance(handoff, dict):
        raise WorkflowError("handoff-invalid", "handoff 必须是对象")
    required = set(contract["handoff"]["fields"])
    if not required.issubset(handoff):
        missing = sorted(required - set(handoff))
        raise WorkflowError("handoff-invalid", "缺 handoff 字段: " + ",".join(missing))
    unknown = sorted(set(handoff) - required)
    if unknown:
        raise WorkflowError("handoff-invalid", "含未知 handoff 字段: " + ",".join(unknown))
    validate_evidence_refs(root, handoff["evidence_refs"])


def command_init(args, root):
    if os.path.exists(os.path.join(root, ".workflow")):
        raise WorkflowError("already-initialized", "状态目录已存在")
    contract = load_contract(root)
    scope = read_json(args.scope)
    validate_scope(root, scope, contract)
    workflow_dir = os.path.join(root, ".workflow")
    os.makedirs(workflow_dir, exist_ok=False)
    try:
        scope_path = state_path(root, "scope.json")
        write_json_atomic(scope_path, scope)
        scope_digest = sha256_file(scope_path)
        contract_digest = contract_hash(root)
        event = event_base(scope["task_id"], 0, scope["initial_stage"], "init", "system", contract_digest)
        raw = write_events_atomic(state_path(root, "events.jsonl"), [event])
        write_json_atomic(state_path(root, "manifest.json"), {
            "task_id": scope["task_id"],
            "epoch": 0,
            "stage": scope["initial_stage"],
            "contract_hash": contract_digest,
            "scope_hash": scope_digest,
            "events_sha256": sha256_bytes(raw),
        })
    except Exception:
        shutil.rmtree(workflow_dir, ignore_errors=True)
        raise
    return {"ok": True, "command": "init", "task_id": scope["task_id"], "epoch": 0, "stage": scope["initial_stage"]}


def state_result(command, state):
    return {
        "ok": not state["blocked"],
        "command": command,
        "task_id": state["scope"]["task_id"],
        "epoch": state["epoch"],
        "stage": state["stage"],
        "approved_current_epoch": state["approved"],
        "blocked": state["blocked"],
    }


def command_status(args, root):
    return state_result("status", load_state(root, allow_stale=True))


def command_check(args, root):
    state = load_state(root, allow_stale=True, check_files=True)
    result = state_result("check", state)
    result["event_count"] = len(state["events"])
    return result


def command_transition(args, root):
    with WorkflowLock(root):
        state = load_state(root, allow_stale=False, check_files=True)
        if not isinstance(args.actor_label, str) or not args.actor_label.strip():
            raise WorkflowError("transition-invalid", "actor_label 不能为空")
        if args.epoch != state["epoch"]:
            raise WorkflowError("stale-epoch", "期望 epoch 与当前不一致", 3)
        contract = state["contract"]
        edge = {(x["from"], x["to"]): x for x in contract["transitions"]}
        if args.to not in contract["stages"]["primary"] or (state["stage"], args.to) not in edge:
            raise WorkflowError("transition-invalid", "非法转换")
        if args.to in contract["stages"]["execution"] and not state["approved"]:
            raise WorkflowError("approval-required", "进入执行阶段需要当前 epoch approve")
        handoff = read_json(args.handoff)
        validate_handoff(root, handoff, contract)
        event = event_base(state["scope"]["task_id"], state["epoch"], args.to, "transition", args.actor_label, state["manifest"]["contract_hash"], handoff, handoff["evidence_refs"])
        event.update({"from_stage": state["stage"], "to_stage": args.to})
        events = state["events"] + [event]
        raw = write_events_atomic(state_path(root, "events.jsonl"), events)
        write_json_atomic(state_path(root, "manifest.json"), {
            "task_id": state["scope"]["task_id"],
            "epoch": state["epoch"],
            "stage": args.to,
            "contract_hash": state["manifest"]["contract_hash"],
            "scope_hash": state["scope_hash"],
            "events_sha256": sha256_bytes(raw),
        })
    return {"ok": True, "command": "transition", "task_id": state["scope"]["task_id"], "epoch": state["epoch"], "stage": args.to}


def command_approve(args, root):
    with WorkflowLock(root):
        if args.recover:
            return command_recover(args, root)
        if not isinstance(args.actor_label, str) or not args.actor_label.strip():
            raise WorkflowError("approval-invalid", "actor_label 不能为空")
        if not isinstance(args.reason, str) or not args.reason.strip():
            raise WorkflowError("approval-invalid", "approve 必须提供 reason")
        state = load_state(root, allow_stale=True, check_files=True)
        if state["blocked"]:
            raise WorkflowError("state-blocked", "状态已阻塞，请使用 --recover")
        if args.epoch != state["epoch"]:
            raise WorkflowError("stale-epoch", "期望 epoch 与当前不一致", 3)
        approval = event_base(state["scope"]["task_id"], state["epoch"] + 1, state["stage"], "approve", args.actor_label, state["manifest"]["contract_hash"])
        approval.update({"reason": args.reason, "identity_verified": False, "approved_stage": state["stage"]})
        events = state["events"] + [approval]
        raw = write_events_atomic(state_path(root, "events.jsonl"), events)
        next_epoch = state["epoch"] + 1
        write_json_atomic(state_path(root, "manifest.json"), {
            "task_id": state["scope"]["task_id"],
            "epoch": next_epoch,
            "stage": state["stage"],
            "contract_hash": state["manifest"]["contract_hash"],
            "scope_hash": state["scope_hash"],
            "events_sha256": sha256_bytes(raw),
        })
    return {"ok": True, "command": "approve", "task_id": state["scope"]["task_id"], "epoch": next_epoch, "stage": state["stage"], "identity_verified": False}


def read_raw_file(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError as exc:
        raise WorkflowError("state-corrupt", str(exc))


def recovery_rel_path(root, value):
    if not isinstance(value, str) or not value or os.path.isabs(value):
        raise WorkflowError("recovery-pending", "恢复事务路径非法")
    workflow_dir = os.path.realpath(os.path.join(root, ".workflow"))
    candidate = os.path.realpath(os.path.join(workflow_dir, value))
    if os.path.commonpath([workflow_dir, candidate]) != workflow_dir:
        raise WorkflowError("recovery-pending", "恢复事务路径越界")
    return candidate


def load_recovery_txn(root):
    txn = read_json(state_path(root, "recovery.txn.json"))
    required = {"archive_rel", "new_rel", "old_sha256", "new_sha256", "old_epoch", "manifest", "new_events"}
    if not isinstance(txn, dict) or not required.issubset(txn):
        raise WorkflowError("recovery-pending", "恢复事务缺字段")
    for field in ("old_sha256", "new_sha256"):
        value = txn[field]
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise WorkflowError("recovery-pending", "恢复事务哈希非法")
    if not isinstance(txn["old_epoch"], int) or isinstance(txn["old_epoch"], bool) or txn["old_epoch"] < 0:
        raise WorkflowError("recovery-pending", "恢复事务 epoch 非法")
    if not isinstance(txn["manifest"], dict):
        raise WorkflowError("recovery-pending", "恢复事务 manifest 非法")
    if not isinstance(txn["new_events"], list) or len(txn["new_events"]) != 2:
        raise WorkflowError("recovery-pending", "恢复事务新事件非法")
    new_manifest = txn["manifest"]
    manifest_required = {"task_id", "epoch", "stage", "contract_hash", "scope_hash", "events_sha256"}
    if not manifest_required.issubset(new_manifest):
        raise WorkflowError("recovery-pending", "恢复事务 manifest 缺字段")
    if new_manifest["events_sha256"] != txn["new_sha256"]:
        raise WorkflowError("recovery-pending", "恢复事务 manifest 哈希不一致")
    if not isinstance(new_manifest["task_id"], str) or not new_manifest["task_id"]:
        raise WorkflowError("recovery-pending", "恢复事务 task_id 非法")
    if not isinstance(new_manifest["stage"], str) or not isinstance(new_manifest["epoch"], int) or isinstance(new_manifest["epoch"], bool):
        raise WorkflowError("recovery-pending", "恢复事务 manifest 状态非法")
    for field in ("contract_hash", "scope_hash", "events_sha256"):
        value = new_manifest[field]
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise WorkflowError("recovery-pending", "恢复事务 manifest 哈希非法")
    archive = recovery_rel_path(root, txn["archive_rel"])
    staged = recovery_rel_path(root, txn["new_rel"])
    return txn, archive, staged


def finish_recovery(root, txn, archive, staged, args):
    if args.epoch != txn["old_epoch"]:
        raise WorkflowError("stale-epoch", "恢复 epoch 与事务不一致", 3)
    if not os.path.exists(archive):
        current_raw = read_raw_file(state_path(root, "events.jsonl"))
        if sha256_bytes(current_raw) != txn["old_sha256"]:
            raise WorkflowError("recovery-pending", "恢复归档缺失且当前日志不是旧日志")
        write_bytes_atomic(archive, current_raw)
    if not os.path.exists(staged):
        staged_raw = ("".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in txn["new_events"])).encode("utf-8")
        if sha256_bytes(staged_raw) != txn["new_sha256"]:
            raise WorkflowError("recovery-pending", "恢复事务新事件哈希不一致")
        write_bytes_atomic(staged, staged_raw)
    archive_raw = read_raw_file(archive)
    staged_raw = read_raw_file(staged)
    if sha256_bytes(archive_raw) != txn["old_sha256"]:
        raise WorkflowError("recovery-pending", "恢复归档哈希不一致")
    if sha256_bytes(staged_raw) != txn["new_sha256"]:
        raise WorkflowError("recovery-pending", "恢复新日志哈希不一致")
    manifest = txn["manifest"]
    contract = load_contract(root)
    scope, scope_digest = load_scope(root, contract)
    if manifest["task_id"] != scope["task_id"] or manifest["scope_hash"] != scope_digest:
        raise WorkflowError("recovery-pending", "恢复事务 scope 与当前不一致")
    if manifest["contract_hash"] != contract_hash(root):
        raise WorkflowError("recovery-pending", "恢复事务 contract 与当前不一致")
    _, recovered_epoch, recovered_stage, _ = parse_events(root, contract, staged_raw, manifest["contract_hash"], check_files=True)
    if recovered_epoch != manifest["epoch"] or recovered_stage != manifest["stage"]:
        raise WorkflowError("recovery-pending", "恢复事务重放结果与 manifest 不一致")
    write_bytes_atomic(state_path(root, "events.jsonl"), staged_raw)
    write_json_atomic(state_path(root, "manifest.json"), manifest)
    try:
        os.unlink(staged)
    except FileNotFoundError:
        pass
    try:
        os.unlink(state_path(root, "recovery.txn.json"))
    except FileNotFoundError:
        pass
    return {
        "ok": True,
        "command": "approve",
        "task_id": manifest["task_id"],
        "epoch": manifest["epoch"],
        "stage": manifest["stage"],
        "recovered": True,
        "identity_verified": False,
    }


def command_recover(args, root):
    if not isinstance(args.reason, str) or not args.reason.strip():
        raise WorkflowError("approval-invalid", "recover 必须提供 reason")
    if not isinstance(args.actor_label, str) or not args.actor_label.strip():
        raise WorkflowError("approval-invalid", "recover 必须提供 actor_label")
    txn_path = state_path(root, "recovery.txn.json")
    if os.path.exists(txn_path):
        txn, archive, staged = load_recovery_txn(root)
        return finish_recovery(root, txn, archive, staged, args)

    contract = load_contract(root)
    manifest = load_manifest(root)
    if args.epoch != manifest["epoch"]:
        raise WorkflowError("stale-epoch", "恢复 epoch 与 manifest 不一致", 3)
    scope, scope_digest = load_scope(root, contract)
    if manifest["task_id"] != scope["task_id"]:
        raise WorkflowError("state-corrupt", "manifest 与 scope task_id 不一致")
    if manifest["stage"] not in contract["stages"]["primary"]:
        raise WorkflowError("state-corrupt", "manifest stage 非法")

    try:
        state = load_state(root, allow_stale=True, check_files=True)
    except WorkflowError as exc:
        if exc.code not in {"state-corrupt", "encoding-invalid", "json-invalid", "file-unreadable"}:
            raise
    else:
        if not state["blocked"]:
            raise WorkflowError("recovery-not-needed", "健康状态不允许 recover")

    events_path = state_path(root, "events.jsonl")
    raw = read_raw_file(events_path)
    old_digest = sha256_bytes(raw)
    archive_name = contract["recovery"]["archive_directory"]
    archive_dir = recovery_rel_path(root, archive_name)
    os.makedirs(archive_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    archive_rel = os.path.join(archive_name, "events-%s-%s-%s.jsonl" % (stamp, time.time_ns(), old_digest[:12])).replace(os.sep, "/")
    archive = recovery_rel_path(root, archive_rel)
    staged_rel = "recovery.new.jsonl"
    staged = recovery_rel_path(root, staged_rel)
    if os.path.exists(staged):
        raise WorkflowError("recovery-pending", "存在未归档的恢复暂存日志")

    current_contract_hash = contract_hash(root)
    recovery_epoch = manifest["epoch"] + 1
    recovery = event_base(manifest["task_id"], recovery_epoch, manifest["stage"], "recovery", args.actor_label, current_contract_hash)
    recovery.update({
        "reason": args.reason,
        "identity_verified": False,
        "recovered_from_epoch": manifest["epoch"],
        "archived_events_sha256": old_digest,
    })
    approve_epoch = recovery_epoch + 1
    approval = event_base(manifest["task_id"], approve_epoch, manifest["stage"], "approve", args.actor_label, current_contract_hash)
    approval.update({
        "reason": args.reason,
        "identity_verified": False,
        "approved_stage": manifest["stage"],
        "recovery_from_epoch": recovery_epoch,
    })
    new_raw = (json.dumps(recovery, ensure_ascii=False, sort_keys=True) + "\n" + json.dumps(approval, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    new_manifest = {
        "task_id": manifest["task_id"],
        "epoch": approve_epoch,
        "stage": manifest["stage"],
        "contract_hash": current_contract_hash,
        "scope_hash": scope_digest,
        "events_sha256": sha256_bytes(new_raw),
    }
    txn = {
        "archive_rel": archive_rel,
        "new_rel": staged_rel,
        "old_sha256": old_digest,
        "new_sha256": sha256_bytes(new_raw),
        "old_epoch": manifest["epoch"],
        "manifest": new_manifest,
        "new_events": [recovery, approval],
    }
    write_json_atomic(txn_path, txn)
    write_bytes_atomic(archive, raw)
    write_bytes_atomic(staged, new_raw)
    return finish_recovery(root, txn, archive, staged, args)


def build_parser():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--root", required=True)
    init.add_argument("--scope", required=True)
    for name in ("status", "check"):
        item = sub.add_parser(name)
        item.add_argument("--root", required=True)
    transition = sub.add_parser("transition")
    transition.add_argument("--root", required=True)
    transition.add_argument("--epoch", required=True, type=int)
    transition.add_argument("--to", required=True)
    transition.add_argument("--handoff", required=True)
    transition.add_argument("--actor-label", default="unknown-caller")
    approve = sub.add_parser("approve")
    approve.add_argument("--root", required=True)
    approve.add_argument("--epoch", required=True, type=int)
    approve.add_argument("--actor-label", required=True)
    approve.add_argument("--reason", required=True)
    approve.add_argument("--recover", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    root = os.path.abspath(args.root)
    try:
        if args.command == "init":
            result = command_init(args, root)
        elif args.command == "status":
            result = command_status(args, root)
        elif args.command == "check":
            result = command_check(args, root)
        elif args.command == "transition":
            result = command_transition(args, root)
        else:
            result = command_approve(args, root)
        emit(result)
        return 0 if result.get("ok") else 1
    except WorkflowError as exc:
        emit({"ok": False, "command": args.command, "error": exc.code, "message": str(exc)})
        return exc.exit_code
    except (OSError, ValueError, KeyError, TypeError) as exc:
        emit({"ok": False, "command": args.command, "error": "internal-error", "message": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
