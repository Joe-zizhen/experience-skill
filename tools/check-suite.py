#!/usr/bin/env python3
"""套件静态守卫（contracts/suite-v1.yaml 的执行器）。

检查：frontmatter（name==目录名、description≤350 字符）、四级标签与绝对词越级、
@latest、UTF-8 无 BOM/无替换字符、相对链接可达、LICENSE 在位、.sh 语法与执行位、
openai.yaml 基本结构。

用法：在仓库根目录跑 `python tools/check-suite.py`。退出码 0 = 全过，1 = 有 ERROR。
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = ["experience", "senior-engineer", "systematic-debugging",
          "5w-ledger-v1-3", "first-principle-v2", "pm"]
TIER_RE = re.compile(r"\*?\*?\[(INV|DEFAULT|HEURISTIC|EXAMPLE)\]\*?\*?")
TEXT_EXT = (".md", ".py", ".sh", ".yaml", ".yml", ".ts", ".toml", ".json", ".txt")
errors = []
warnings = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, "/")


def load_abs_words():
    with open(os.path.join(ROOT, "contracts", "suite-v1.yaml"), encoding="utf-8") as f:
        t = f.read()
    m = re.search(r"absolute_words:\s*\[([^\]]*)\]", t)
    if not m:
        err("contracts/suite-v1.yaml 缺 absolute_words")
        return []
    return [w.strip() for w in m.group(1).split(",") if w.strip()]


def check_encoding():
    for dirpath, _, files in os.walk(ROOT):
        if ".git" in dirpath.split(os.sep):
            continue
        for fn in files:
            if not fn.endswith(TEXT_EXT) and fn not in ("LICENSE",):
                continue
            p = os.path.join(dirpath, fn)
            b = open(p, "rb").read()
            if b.startswith(b"\xef\xbb\xbf"):
                err("BOM: " + rel(p))
            if b"\xef\xbf\xbd" in b:
                err("替换字符 U+FFFD: " + rel(p))
            try:
                b.decode("utf-8")
            except UnicodeDecodeError:
                err("非 UTF-8: " + rel(p))


def check_frontmatter():
    for s in SKILLS:
        p = os.path.join(ROOT, s, "SKILL.md")
        if not os.path.exists(p):
            err("缺 SKILL.md: " + s)
            continue
        t = open(p, encoding="utf-8").read()
        m = re.match(r"^---\s*\n(.*?)\n---", t, re.S)
        if not m:
            err("frontmatter 缺失: " + s)
            continue
        fm = m.group(1)
        nm = re.search(r"^name:\s*(.+?)\s*$", fm, re.M)
        if not nm or nm.group(1) != s:
            err("name 与目录名不符: %s -> %s" % (s, nm.group(1) if nm else "NONE"))
        ds = re.search(r'^description:\s*"(.*)"\s*$', fm, re.M)
        if not ds:
            err("description 缺失或格式不对（须双引号单行）: " + s)
        elif len(ds.group(1)) > 350:
            err("description 超 350 字符(%d): %s" % (len(ds.group(1)), s))


def iter_skill_md():
    for s in SKILLS:
        for dirpath, _, files in os.walk(os.path.join(ROOT, s)):
            for fn in files:
                if fn.endswith(".md"):
                    yield os.path.join(dirpath, fn)


def check_tiers(words):
    """绝对词只许活在当前章节档 = INV。

    章节档只看标题上的 [INV]/[DEFAULT]/[HEURISTIC]。[EXAMPLE] 只管它所在那一行，
    不改后面整节的档——否则 INV 段里插一句示例，后面的红线会全部误报越级。
    行内 `code` 不参与绝对词扫描（指针原文、命令字面量）。
    """
    for p in iter_skill_md():
        cur = None
        in_code = False
        in_fm = False
        fm_done = False
        for i, line in enumerate(open(p, encoding="utf-8"), 1):
            if i == 1 and line.strip() == "---":
                in_fm = True
                continue
            if in_fm and line.strip() == "---":
                in_fm = False
                fm_done = True
                continue
            if in_fm:
                continue  # frontmatter 是元数据，不做规则层判定
            if line.lstrip().startswith("```"):
                in_code = not in_code
            marks = TIER_RE.findall(line)
            if len(marks) >= 2:
                continue  # 图例/目录行（多标签并列）豁免
            if marks and marks[0] != "EXAMPLE":
                cur = marks[0]
            if in_code:
                continue
            scanned = re.sub(r"`[^`]*`", "", line)
            hit = [w for w in words if w in scanned]
            if hit and cur != "INV":
                err("绝对词越级 %s: %s:%d: %s" % (hit, rel(p), i, line.strip()[:60]))


def check_latest():
    for dirpath, _, files in os.walk(ROOT):
        if ".git" in dirpath.split(os.sep):
            continue
        for fn in files:
            if not fn.endswith(TEXT_EXT):
                continue
            p = os.path.join(dirpath, fn)
            if rel(p).startswith("tools/check-"):
                continue  # 检查器自身必然包含该字面量（作为检查目标）
            for i, line in enumerate(open(p, encoding="utf-8", errors="ignore"), 1):
                if "@latest" in line and "禁" not in line:
                    err("@latest 出现: %s:%d" % (rel(p), i))


def check_links():
    link_re = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(#[^)]*)?\)")
    for p in iter_skill_md():
        base = os.path.dirname(p)
        for i, line in enumerate(open(p, encoding="utf-8"), 1):
            for m in link_re.finditer(line):
                target = m.group(1)
                if "://" in target or target.startswith("mailto:"):
                    continue
                if not os.path.exists(os.path.normpath(os.path.join(base, target))):
                    err("死链接: %s:%d -> %s" % (rel(p), i, target))


def check_license_and_scripts():
    if not os.path.exists(os.path.join(ROOT, "LICENSE")):
        err("缺根 LICENSE")
    if not os.path.exists(os.path.join(ROOT, "systematic-debugging", "LICENSE")):
        err("缺 systematic-debugging/LICENSE")
    modes = {}
    try:
        out = subprocess.run(["git", "ls-files", "-s"], cwd=ROOT,
                             capture_output=True, text=True).stdout
        for line in out.splitlines():
            parts = line.split(None, 3)
            if len(parts) == 4:
                modes[parts[3]] = parts[0]
    except Exception:
        pass
    for s in SKILLS:
        for dirpath, _, files in os.walk(os.path.join(ROOT, s)):
            for fn in files:
                p = os.path.join(dirpath, fn)
                if fn.endswith(".sh"):
                    try:
                        r = subprocess.run(["bash", "-n", p], capture_output=True)
                        if r.returncode != 0:
                            err("bash 语法错误: %s: %s" % (rel(p), r.stderr.decode("utf-8", "ignore")[:120]))
                    except FileNotFoundError:
                        warn("无 bash，跳过语法检查: " + rel(p))
                    mode = modes.get(rel(p))
                    if mode and mode != "100755":
                        err(".sh 缺执行位(%s): %s" % (mode, rel(p)))
                if fn == "openai.yaml":
                    t = open(p, encoding="utf-8").read()
                    if "interface:" not in t or "policy:" not in t:
                        err("openai.yaml 结构异常: " + rel(p))


def check_constitution():
    boot = os.path.join(ROOT, "contracts", "boot.md")
    if not os.path.exists(boot):
        err("缺 contracts/boot.md")
    else:
        t = open(boot, encoding="utf-8").read()
        for s in SKILLS:
            if s not in t:
                err("boot.md 未点名 skill: " + s)
        if "看起来做完了" not in t:
            err("boot.md 未写定律")
    readme_p = os.path.join(ROOT, "README.md")
    readme = ""
    if os.path.exists(readme_p):
        readme = open(readme_p, encoding="utf-8").read()
        if "contracts/suite-v1.yaml" not in readme:
            err("README 未指向 contracts/suite-v1.yaml 为路由权威")
        if "看起来做完了" not in readme:
            err("README 未写定律")
    suite_p = os.path.join(ROOT, "contracts", "suite-v1.yaml")
    if not os.path.exists(suite_p):
        err("缺 contracts/suite-v1.yaml")
        return
    suite = open(suite_p, encoding="utf-8").read()
    skills_block = suite.split("skills:", 1)[-1].split("routing:", 1)[0]
    for s in SKILLS:
        if s + ":" not in skills_block:
            err("suite skills 缺: " + s)
    if "path: contracts/boot.md" not in suite.replace("\\", "/"):
        err("suite 未登记 boot.md")
    if "\nlaw:" not in suite and not suite.lstrip().startswith("law:"):
        err("suite 未登记 law")
    if "看起来做完了" not in suite:
        err("suite law 未写定律原文")
    if "list_death" not in suite:
        err("suite 未写闭清单死因")
    for s in SKILLS:
        p = os.path.join(ROOT, s, "SKILL.md")
        if not os.path.exists(p):
            continue
        body = open(p, encoding="utf-8").read()
        if "套件定律" not in body and "suite law" not in body:
            err("SKILL.md 未声明套件定律推论: " + s)


def main():
    words = load_abs_words()
    check_encoding()
    check_frontmatter()
    if words:
        check_tiers(words)
    check_latest()
    check_links()
    check_license_and_scripts()
    check_constitution()
    for w in warnings:
        print("WARN: " + w)
    if errors:
        for e in errors:
            print("ERROR: " + e)
        print("\n%d ERROR / %d WARN" % (len(errors), len(warnings)))
        return 1
    print("ALL CHECKS PASSED (%d WARN)" % len(warnings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
