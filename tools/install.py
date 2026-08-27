#!/usr/bin/env python3
"""Myskills 安装器（替代 cp -r）：暂存 → 校验 → 备份 → 原子替换 → 读回哈希；失败回滚。

用法（仓库根目录外也可跑）：
  python tools/install.py --source <仓库目录> --host-dir <宿主 skills 目录>
      [--skills pm senior-engineer ...]   # 默认全部六个
      [--state-dir <状态目录>]            # 默认 <host-dir>/.install-state
      [--verify-only]                     # 只读回校验，不安装
      [--dry-run]

状态文件：<state-dir>/install-state.json（每 skill 的 sha256 清单与时间戳）。
退出码：0 成功；1 失败（已回滚到安装前状态）。
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time

ALL_SKILLS = ["experience", "senior-engineer", "systematic-debugging",
              "5w-ledger-v1-3", "first-principle-v2", "pm"]
SKIP_NAMES = {".git", "__pycache__", ".DS_Store"}
BOOT_START = "<!-- myskills-boot:start -->"
BOOT_END = "<!-- myskills-boot:end -->"


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


def check_manifest(base_dir, manifest):
    """读回校验：返回错误列表（缺失/哈希不符/多出文件）。"""
    errs = []
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
        return json.load(open(state_path(state_dir), encoding="utf-8"))
    except Exception:
        return {}


def save_state(state_dir, state):
    os.makedirs(state_dir, exist_ok=True)
    with open(state_path(state_dir), "w", encoding="utf-8", newline="") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def host_instruction_file(host_dir):
    parent = os.path.dirname(host_dir)
    name = os.path.basename(parent).lower()
    if name == ".claude":
        return os.path.join(parent, "CLAUDE.md")
    if name in (".codex", ".agents"):
        return os.path.join(parent, "AGENTS.md")
    return None


def inject_boot(source, host_dir, dry_run=False):
    boot_src = os.path.join(source, "contracts", "boot.md")
    if not os.path.isfile(boot_src):
        print("boot: 无 contracts/boot.md，跳过")
        return
    dest = host_instruction_file(host_dir)
    if not dest:
        print("boot: 未识别宿主入口（上一级不是 .claude/.agents/.codex），跳过")
        return
    body = open(boot_src, encoding="utf-8").read().strip()
    block = "%s\n%s\n%s\n" % (BOOT_START, body, BOOT_END)
    if dry_run:
        print("dry-run boot -> %s" % dest)
        return
    existing = ""
    if os.path.isfile(dest):
        existing = open(dest, encoding="utf-8").read()
    if BOOT_START in existing and BOOT_END in existing:
        pre = existing.split(BOOT_START, 1)[0]
        post = existing.split(BOOT_END, 1)[1]
        if post.startswith("\n"):
            post = post[1:]
        new = pre + block + post
    else:
        new = block + ("\n" if existing else "") + existing
    tmp = dest + ".tmp-boot"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    os.replace(tmp, dest)
    print("boot -> %s" % dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="skills 仓库目录（含各 skill 子目录）")
    ap.add_argument("--host-dir", required=True, help="宿主 skills 目录")
    ap.add_argument("--skills", nargs="*", default=ALL_SKILLS)
    ap.add_argument("--state-dir", default=None)
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    source = os.path.abspath(args.source)
    host_dir = os.path.abspath(args.host_dir)
    state_dir = os.path.abspath(args.state_dir) if args.state_dir else os.path.join(host_dir, ".install-state")
    state = load_state(state_dir)

    if args.verify_only:
        bad = []
        for s in args.skills:
            entry = state.get(s)
            if not entry:
                bad.append("%s: 无安装记录" % s)
                continue
            errs = check_manifest(os.path.join(host_dir, s), entry["files"])
            bad.extend("%s: %s" % (s, e) for e in errs)
        if bad:
            print("VERIFY FAILED")
            for b in bad:
                print("  " + b)
            return 1
        print("VERIFY OK (%d skills)" % len(args.skills))
        return 0

    os.makedirs(host_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    stage_root = os.path.join(host_dir, ".install-stage-" + ts)
    backup_root = os.path.join(state_dir, "backup-" + ts)
    staged = {}   # skill -> (stage 路径, manifest)
    backed_up = []
    installed = []

    try:
        # 1 暂存 + 清单 + 暂存后校验
        for s in args.skills:
            src = os.path.join(source, s)
            if not os.path.isdir(src):
                raise RuntimeError("源缺 skill 目录: " + s)
            manifest = build_manifest(src)
            dst = os.path.join(stage_root, s)
            shutil.copytree(src, dst)
            errs = check_manifest(dst, manifest)
            if errs:
                raise RuntimeError("暂存校验失败 %s: %s" % (s, errs[:3]))
            staged[s] = (dst, manifest)
            print("staged %s (%d files)" % (s, len(manifest)))

        if args.dry_run:
            print("dry-run: 校验通过，未改动宿主目录")
            inject_boot(source, host_dir, dry_run=True)
            return 0

        # 2 备份现有同名目录
        for s in args.skills:
            cur = os.path.join(host_dir, s)
            if os.path.exists(cur):
                os.makedirs(backup_root, exist_ok=True)
                shutil.move(cur, os.path.join(backup_root, s))
                backed_up.append(s)
                print("backup %s" % s)

        # 3 原子替换（同卷 move）+ 逐个读回
        for s, (dst, manifest) in staged.items():
            shutil.move(dst, os.path.join(host_dir, s))
            installed.append(s)
            errs = check_manifest(os.path.join(host_dir, s), manifest)
            if errs:
                raise RuntimeError("读回校验失败 %s: %s" % (s, errs[:3]))
            state[s] = {"sha256_root": hashlib.sha256(
                json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
                "files": manifest, "installed_at": ts}
            print("installed %s (readback ok)" % s)

        save_state(state_dir, state)
        shutil.rmtree(backup_root, ignore_errors=True)
        try:
            inject_boot(source, host_dir, dry_run=False)
        except Exception as be:
            print("boot 写入失败（skill 已安装）: %s" % be)
        print("DONE: %d skills installed, state -> %s" % (len(installed), state_path(state_dir)))
        return 0

    except Exception as e:
        print("INSTALL FAILED: %s" % e)
        print("回滚中…")
        for s in installed:
            shutil.rmtree(os.path.join(host_dir, s), ignore_errors=True)
        for s in backed_up:
            src_b = os.path.join(backup_root, s)
            if os.path.exists(src_b):
                shutil.move(src_b, os.path.join(host_dir, s))
        shutil.rmtree(stage_root, ignore_errors=True)
        print("已回滚到安装前状态")
        return 1
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
