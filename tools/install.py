#!/usr/bin/env python3
"""Myskills 安装器（替代 cp -r）：暂存 → 校验 → 备份 → 原子替换 → 读回哈希；失败回滚。

用法（仓库根目录外也可跑）：
  python tools/install.py --source <仓库目录> --host-dir <宿主 skills 目录>
      [--skills pm lean-engineer ...]   # 默认装齐 ALL_SKILLS
      [--state-dir <状态目录>]            # 默认 <host-dir>/.install-state
      [--verify-only]                     # 只读回校验，不安装
      [--dry-run]

状态文件：<state-dir>/install-state.json（每 skill 的 sha256 清单与时间戳）。
退出码：0 成功；1 失败。恢复不完整时明确报告，并保留原备份供处理。
"""
import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import time

ALL_SKILLS = ["experience", "lean-engineer", "systematic-debugging",
              "5w-ledger-v1-3", "first-principle-v2", "pm",
              "excellence"]
SKIP_NAMES = {".git", "__pycache__", ".DS_Store", "node_modules", ".stryker-tmp",
              "reports", "coverage", ".pytest_cache", ".quality-venv"}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(skill_dir):
    """返回 {相对路径: sha256}（skill 目录内全部文件）。"""
    manifest = {}
    for dirpath, dirs, files in os.walk(skill_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_NAMES]
        for fn in files:
            if fn in SKIP_NAMES:
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, skill_dir).replace(os.sep, "/")
            manifest[rel] = sha256_file(p)
    return manifest


def _skill_directory_errors(base_dir):
    if not os.path.isdir(base_dir):
        return ["缺 skill 目录: " + base_dir]
    entry = os.path.join(base_dir, "SKILL.md")
    try:
        info = os.lstat(entry)
    except OSError as error:
        return ["缺或不可读 SKILL.md: %s: %s" % (entry, error)]
    reparse = getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if not stat.S_ISREG(info.st_mode) or reparse:
        return ["SKILL.md 应为普通文件: " + entry]
    return []


def _valid_manifest_item(name, digest):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        return False
    if any(part in ("", ".", "..") for part in name.split("/")):
        return False
    return isinstance(digest, str) and len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)


def _manifest_errors(manifest):
    if not isinstance(manifest, dict) or not manifest:
        return ["安装清单为空或结构无效"]
    if "SKILL.md" not in manifest:
        return ["安装清单缺 SKILL.md"]
    if any(not _valid_manifest_item(name, digest) for name, digest in manifest.items()):
        return ["安装清单路径或哈希无效"]
    return []

def check_manifest(base_dir, manifest):
    """读回校验：返回错误列表（缺失/哈希不符/多出文件）。"""
    errs = _skill_directory_errors(base_dir) + _manifest_errors(manifest)
    if errs:
        return errs
    seen = set()
    for dirpath, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_NAMES]
        for fn in files:
            if fn in SKIP_NAMES:
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, base_dir).replace(os.sep, "/")
            seen.add(rel)
            if rel not in manifest:
                errs.append("多出文件: " + rel)
            elif sha256_file(p) != manifest[rel]:
                errs.append("哈希不符: " + rel)
    for rel in manifest:
        if rel not in seen:
            errs.append("缺失: " + rel)
    return errs


def state_path(state_dir):
    return os.path.join(state_dir, "install-state.json")


def load_state(state_dir):
    try:
        with open(state_path(state_dir), encoding="utf-8") as handle:
            state = json.load(handle)
    except FileNotFoundError:
        return {}
    if not isinstance(state, dict):
        raise ValueError("安装记录根节点应为对象")
    return state

def save_state(state_dir, state):
    os.makedirs(state_dir, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".install-state-", suffix=".tmp", dir=state_dir)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        with open(temporary, encoding="utf-8") as handle:
            if json.load(handle) != state:
                raise RuntimeError("安装记录暂存读回不一致")
        os.replace(temporary, state_path(state_dir))
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)

def _parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="skills 仓库目录（含各 skill 子目录）")
    ap.add_argument("--host-dir", required=True, help="宿主 skills 目录")
    ap.add_argument("--skills", nargs="*", default=ALL_SKILLS)
    ap.add_argument("--state-dir", default=None)
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    return ap.parse_args()


def _verify_skills(host_dir, skills, state):
    bad = []
    for skill in skills:
        entry = state.get(skill)
        if not isinstance(entry, dict) or "files" not in entry:
            bad.append("%s: 无安装记录或记录结构无效" % skill)
            continue
        errors = check_manifest(os.path.join(host_dir, skill), entry["files"])
        bad.extend("%s: %s" % (skill, error) for error in errors)
    if bad:
        print("VERIFY FAILED")
        for error in bad:
            print("  " + error)
        return 1
    print("VERIFY OK (%d skills)" % len(skills))
    return 0


def _stage_skills(source, stage_root, skills):
    staged = {}
    for skill in skills:
        src = os.path.join(source, skill)
        source_errors = _skill_directory_errors(src)
        if source_errors:
            raise RuntimeError("源 skill 无效 %s: %s" % (skill, source_errors))
        manifest = build_manifest(src)
        if _manifest_errors(manifest):
            raise RuntimeError("源安装清单为空或无效: " + skill)
        dst = os.path.join(stage_root, skill)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*SKIP_NAMES))
        errors = check_manifest(dst, manifest)
        if errors:
            raise RuntimeError("暂存校验失败 %s: %s" % (skill, errors[:3]))
        staged[skill] = (dst, manifest)
        print("staged %s (%d files)" % (skill, len(manifest)))
    return staged


def _backup_skills(host_dir, backup_root, skills, backed_up):
    for skill in skills:
        current = os.path.join(host_dir, skill)
        if os.path.exists(current):
            if not backed_up:
                os.makedirs(backup_root, exist_ok=False)
            shutil.move(current, os.path.join(backup_root, skill))
            backed_up.append(skill)
            print("backup %s" % skill)


def _activate_skills(host_dir, staged, installed, state, timestamp):
    for skill, (source, manifest) in staged.items():
        shutil.move(source, os.path.join(host_dir, skill))
        installed.append(skill)
        errors = check_manifest(os.path.join(host_dir, skill), manifest)
        if errors:
            raise RuntimeError("读回校验失败 %s: %s" % (skill, errors[:3]))
        state[skill] = {"sha256_root": hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode("utf-8")).hexdigest(),
            "files": manifest, "installed_at": timestamp}
        print("installed %s (readback ok)" % skill)


def _restore_backup(host_dir, backup_root, skill):
    target = os.path.join(host_dir, skill)
    backup = os.path.join(backup_root, skill)
    if os.path.lexists(target):
        raise RuntimeError("恢复目标仍存在，保留备份: " + target)
    if not os.path.isdir(backup):
        raise RuntimeError("恢复备份不存在: " + backup)
    expected = build_manifest(backup)
    shutil.copytree(backup, target)
    if build_manifest(target) != expected:
        raise RuntimeError("恢复读回不一致，保留备份: " + target)


def _rollback_skills(host_dir, backup_root, installed, backed_up):
    errors = []
    for skill in installed:
        target = os.path.join(host_dir, skill)
        try:
            if os.path.lexists(target):
                shutil.rmtree(target)
        except OSError as error:
            errors.append("移除新安装失败 %s: %s" % (target, error))
    for skill in backed_up:
        try:
            _restore_backup(host_dir, backup_root, skill)
        except Exception as error:
            errors.append("恢复 %s 失败: %s" % (skill, error))
    return errors

def _install_skills(source, host_dir, state_dir, skills, dry_run, state):
    os.makedirs(host_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    stage_root = tempfile.mkdtemp(prefix=".install-stage-" + timestamp + "-", dir=host_dir)
    backup_name = "backup-" + os.path.basename(stage_root)[len(".install-stage-"):]
    backup_root = os.path.join(state_dir, backup_name)
    backed_up = []
    installed = []
    try:
        staged = _stage_skills(source, stage_root, skills)
        if dry_run:
            print("dry-run: 暂存校验通过，未替换已安装 skill")
            return 0
        _backup_skills(host_dir, backup_root, skills, backed_up)
        _activate_skills(host_dir, staged, installed, state, timestamp)
        save_state(state_dir, state)
    except Exception as error:
        print("INSTALL FAILED: %s" % error)
        print("回滚中…")
        recovery_errors = _rollback_skills(host_dir, backup_root, installed, backed_up)
        if recovery_errors:
            print("恢复不完整；原备份保留在: " + backup_root)
            for recovery_error in recovery_errors:
                print("  " + recovery_error)
        else:
            print("已回滚到安装前状态")
            if backed_up:
                print("恢复备份保留在: " + backup_root)
        return 1
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)
    shutil.rmtree(backup_root, ignore_errors=True)
    print("DONE: %d skills installed, state -> %s" % (len(installed), state_path(state_dir)))
    return 0

def main():
    args = _parse_args()
    source = os.path.abspath(args.source)
    host_dir = os.path.abspath(args.host_dir)
    state_dir = os.path.abspath(args.state_dir) if args.state_dir else os.path.join(host_dir, ".install-state")
    try:
        state = load_state(state_dir)
    except (OSError, ValueError) as error:
        print("INSTALL FAILED: 安装记录不可读或无效: %s" % error)
        return 1
    if args.verify_only:
        return _verify_skills(host_dir, args.skills, state)
    return _install_skills(source, host_dir, state_dir, args.skills, args.dry_run, state)


if __name__ == "__main__":
    sys.exit(main())
