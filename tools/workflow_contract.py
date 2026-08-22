#!/usr/bin/env python3
"""读取、生成和校验 workflow.json 的最小契约层。"""
import hashlib
import json
import os
import re
import tempfile


SUITE_REL = "contracts/suite-v1.yaml"
WORKFLOW_SOURCE_REL = "contracts/workflow.yaml"
WORKFLOW_REL = "contracts/workflow.json"
TRANSITIONS_RE = re.compile(r"^workflow_transitions:\s*(\[.*\])\s*$", re.M)


class ContractError(Exception):
    """契约源或生成物不满足结构约束。"""


def read_utf8(path):
    with open(path, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        raise ContractError("BOM: " + path)
    text = data.decode("utf-8")
    if "\ufffd" in text:
        raise ContractError("替换字符 U+FFFD: " + path)
    return text


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    with open(path, "rb") as f:
        return sha256_bytes(f.read())


def canonical_json(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_bytes_atomic(path, data):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path):
    try:
        return json.loads(read_utf8(path))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ContractError("JSON 无法读取: %s: %s" % (path, exc))


def _parse_transitions(suite_text):
    matches = TRANSITIONS_RE.findall(suite_text)
    if len(matches) != 1:
        raise ContractError("suite-v1.yaml 缺少唯一 workflow_transitions")
    try:
        transitions = json.loads(matches[0])
    except ValueError as exc:
        raise ContractError("workflow_transitions 不是 JSON 兼容列表: %s" % exc)
    if not isinstance(transitions, list) or not transitions:
        raise ContractError("workflow_transitions 必须是非空列表")
    seen = set()
    for item in transitions:
        if not isinstance(item, dict) or set(item) != {"from", "to", "kind"}:
            raise ContractError("workflow_transitions 项字段错误")
        if not all(isinstance(item[k], str) and item[k] for k in item):
            raise ContractError("workflow_transitions 项值必须是非空字符串")
        if item["kind"] not in {"forward", "back"}:
            raise ContractError("workflow_transitions kind 必须是 forward 或 back")
        edge = (item["from"], item["to"])
        if edge in seen:
            raise ContractError("workflow_transitions 存在重复边: %s -> %s" % edge)
        seen.add(edge)
    return transitions


def build_contract(root):
    suite_path = os.path.join(root, SUITE_REL.replace("/", os.sep))
    source_path = os.path.join(root, WORKFLOW_SOURCE_REL.replace("/", os.sep))
    suite_bytes = read_utf8(suite_path).encode("utf-8")
    source_bytes = read_utf8(source_path).encode("utf-8")
    suite_text = suite_bytes.decode("utf-8")
    source = json.loads(source_bytes.decode("utf-8"))
    if not isinstance(source, dict) or set(source) != {"schema", "workflow"}:
        raise ContractError("workflow.yaml 必须是严格 JSON 兼容的 YAML 子集")
    policy = source["workflow"]
    if not isinstance(policy, dict):
        raise ContractError("workflow.workflow 必须是对象")
    for field in ("scope", "handoff", "exit_codes", "recovery"):
        if not isinstance(policy.get(field), dict):
            raise ContractError("workflow.%s 缺失或不是对象" % field)
    transitions = _parse_transitions(suite_text)
    stages = policy.get("stages")
    background = policy.get("background_stages", [])
    if not isinstance(stages, list) or not stages or any(not isinstance(x, str) for x in stages):
        raise ContractError("workflow.stages 必须是非空字符串列表")
    if len(set(stages)) != len(stages):
        raise ContractError("workflow.stages 不得重复")
    initial_stage = policy.get("initial_stage")
    if initial_stage not in stages:
        raise ContractError("initial_stage 必须属于 stages")
    if not isinstance(background, list) or any(not isinstance(x, str) for x in background):
        raise ContractError("background_stages 必须是字符串列表")
    if any(x in stages for x in background):
        raise ContractError("background stage 不得出现在 primary stages")
    for item in transitions:
        if item["from"] not in stages or item["to"] not in stages:
            raise ContractError("转换引用未知 stage: %s -> %s" % (item["from"], item["to"]))
    execution = policy.get("execution_stages")
    if not isinstance(execution, list) or any(not isinstance(x, str) or x not in stages for x in execution):
        raise ContractError("execution_stages 必须是 stages 子集")
    if initial_stage in execution:
        raise ContractError("initial_stage 不得绕过执行批准门")
    event = policy.get("event")
    allowed_types = event.get("allowed_types") if isinstance(event, dict) else None
    if not isinstance(allowed_types, list) or not allowed_types or any(not isinstance(x, str) or not x for x in allowed_types):
        raise ContractError("event.allowed_types 缺失或非法")
    if len(set(allowed_types)) != len(allowed_types):
        raise ContractError("event.allowed_types 不得重复")
    required_event = policy.get("event", {}).get("required_fields")
    required_handoff = policy.get("handoff", {}).get("fields")
    if not isinstance(required_event, list) or not required_event:
        raise ContractError("event.required_fields 缺失")
    if not isinstance(required_handoff, list) or not required_handoff:
        raise ContractError("handoff.fields 缺失")
    if any(not isinstance(x, str) or not x for x in required_event) or len(set(required_event)) != len(required_event):
        raise ContractError("event.required_fields 必须是唯一字符串列表")
    if any(not isinstance(x, str) or not x for x in required_handoff) or len(set(required_handoff)) != len(required_handoff):
        raise ContractError("handoff.fields 必须是唯一字符串列表")
    epoch = policy.get("epoch")
    if not isinstance(epoch, dict):
        raise ContractError("epoch 规则缺失")
    increment_events = epoch.get("increment_events")
    if not isinstance(increment_events, list) or not increment_events:
        raise ContractError("epoch.increment_events 缺失")
    if any(item not in allowed_types for item in increment_events):
        raise ContractError("epoch.increment_events 含未知事件")
    if epoch.get("record_after_increment") is not True:
        raise ContractError("epoch 必须记录递增后的当前值")
    exit_codes = policy.get("exit_codes")
    if not isinstance(exit_codes, dict) or not all(isinstance(value, int) and not isinstance(value, bool) for value in exit_codes.values()):
        raise ContractError("exit_codes 必须是整数映射")
    recovery = policy.get("recovery")
    if not isinstance(recovery, dict) or recovery.get("reason_required") is not True or recovery.get("manual_event_edit") is not False:
        raise ContractError("recovery 规则缺失或不安全")
    if not isinstance(recovery.get("archive_directory"), str) or not recovery["archive_directory"]:
        raise ContractError("recovery.archive_directory 缺失")
    if not isinstance(recovery.get("restore_rule"), str) or not recovery["restore_rule"]:
        raise ContractError("recovery.restore_rule 缺失")
    return {
        "schema": source["schema"],
        "source_hashes": {
            SUITE_REL: sha256_bytes(suite_bytes),
            WORKFLOW_SOURCE_REL: sha256_bytes(source_bytes),
        },
        "scope": policy["scope"],
        "stages": {
            "initial_stage": initial_stage,
            "primary": stages,
            "execution": execution,
            "background": background,
        },
        "transitions": transitions,
        "handoff": policy["handoff"],
        "event": event,
        "epoch": epoch,
        "exit_codes": exit_codes,
        "recovery": recovery,
    }


def generated_bytes(root):
    return canonical_json(build_contract(root))


def check_generated(root):
    path = os.path.join(root, WORKFLOW_REL.replace("/", os.sep))
    try:
        expected = generated_bytes(root)
    except (ContractError, ValueError, OSError, KeyError, TypeError) as exc:
        return [str(exc)]
    try:
        actual = open(path, "rb").read()
    except OSError as exc:
        return ["缺生成物 %s: %s" % (WORKFLOW_REL, exc)]
    errors = []
    if actual.startswith(b"\xef\xbb\xbf"):
        errors.append("生成物含 BOM: " + WORKFLOW_REL)
    if b"\xef\xbf\xbd" in actual:
        errors.append("生成物含替换字符 U+FFFD: " + WORKFLOW_REL)
    if actual != expected:
        errors.append("生成物与源契约不一致: " + WORKFLOW_REL)
    try:
        value = json.loads(actual.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        errors.append("生成物不是 UTF-8 JSON: %s" % exc)
        return errors
    if not isinstance(value, dict):
        errors.append("生成物根节点不是对象")
    return errors


def load_generated(root):
    errors = check_generated(root)
    if errors:
        raise ContractError("; ".join(errors))
    path = os.path.join(root, WORKFLOW_REL.replace("/", os.sep))
    return read_json(path)
