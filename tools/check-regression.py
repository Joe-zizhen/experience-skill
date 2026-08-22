#!/usr/bin/env python3
"""静态回归守卫：把三轮对抗评审的修复固化为断言，防回潮。

用法：在仓库根目录跑 `python tools/check-regression.py`。退出码 0 = 全过。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (相对路径, 必须包含任一都没有即错, 必须不包含任一出现即错)
CHECKS = [
    ("systematic-debugging/SKILL.md",
     ["[INV]", "grep -q IDENTITY", "Stop-loss is not a fix", "minimal sufficient causal"],
     ["${IDENTITY:+SET}${IDENTITY:-UNSET}", "env | grep IDENTITY ||", "Loop Diagnosis-Handoff",
      "95%", "15-30 minutes", "This is NOT a failed hypothesis - this is a wrong architecture"]),
    ("systematic-debugging/defense-in-depth.md",
     ["tmpDir + sep", "[DEFAULT]"], []),
    ("systematic-debugging/isolate-polluter.sh",
     ["already exists before any test ran", "TEST_RUNNER"], []),
    ("systematic-debugging/agents/openai.yaml",
     ["Systematic Debugging"], ["Loop"]),
    ("systematic-debugging/LICENSE",
     ["Jesse Vincent", "isolate-polluter"], []),
    ("senior-engineer/SKILL.md",
     ["[INV]", "[HEURISTIC]", "禁止把 skill 指针当作规则唯一来源", "显式 setup"],
     ["只写指针，不写规则全文", "路由只写指针", "@upstash/context7-mcp@latest"]),
    ("experience/SKILL.md",
     ["只读任务零写入", "schema 1", "数据目录", "不强占首行"], []),
    ("experience/references/hook-setup.md",
     ["trusted-roots", "symlink", "UTF-8"], []),
    ("5w-ledger-v1-3/SKILL.md",
     ["REFUTED", "UNRESOLVED", "Prefix exemption", "Source type"],
     ["`REJECT`"]),
    ("pm/SKILL.md",
     ["当前请求本身就是拍板", "替拍负面清单", "只抽公开契约"],
     ["档位只升不降"]),
    ("first-principle-v2/SKILL.md",
     ["references/constraint-taxonomy.md", "UNKNOWN", "Implementation boundary"], []),
    ("contracts/suite-v1.yaml",
     ["single_primary_driver", "absolute_words"], []),
    ("tools/check-suite.py",
     ["absolute_words"], []),
    ("evals/trigger-prompts.md",
     ["5w-ledger-v1-3"], ["5w-ledger-v1-2"]),
    ("LICENSE",
     ["Joe-zizhen", "systematic-debugging"], []),
    ("README.md",
     ["5w-ledger-v1-3", "isolate-polluter"], ["find-polluter.sh"]),
    ("contracts/suite-v1.yaml",
     ["workflow_transitions"], ["handoff:"]),
    ("contracts/workflow.yaml",
     ["\"increment_events\"", "\"record_after_increment\": true", "\"restore_rule\"", "\"manual_event_edit\": false"],
     ["workflow_transitions"]),
    ("contracts/workflow.json",
     ["\"source_hashes\"", "\"transitions\"", "\"increment_events\"", "\"restore_rule\""], []),
    ("tools/workflow_contract.py",
     ["workflow_transitions", "record_after_increment", "生成物与源契约不一致", "read_utf8"], ["yaml.safe_load"]),
    ("tools/workflow.py",
     ["approval-required", "recovery-not-needed", "recovery.txn.json", "identity_verified", "os.path.realpath"], []),
    ("tools/check-suite.py",
     ["check_generated", "handoff 字段权威", "唯一生成物"], []),
    ("tools/selftest-workflow.py",
     ["test_not_in_scope", "test_lifecycle", "test_contract_guards", "WORKFLOW SELFTEST PASSED"], []),
]


def main():
    failures = []
    assertion_count = 0
    for relpath, must, must_not in CHECKS:
        p = os.path.join(ROOT, relpath)
        if not os.path.exists(p):
            failures.append("缺文件: " + relpath)
            continue
        text = open(p, encoding="utf-8").read()
        for s in must:
            assertion_count += 1
            if s not in text:
                failures.append("%s: 缺断言内容 %r" % (relpath, s))
        for s in must_not:
            assertion_count += 1
            if s in text:
                failures.append("%s: 回潮内容 %r" % (relpath, s))
    if failures:
        for f in failures:
            print("ERROR: " + f)
        print("\n%d 项回归失败" % len(failures))
        return 1
    print("ALL REGRESSION CHECKS PASSED (%d files, %d assertions)" % (len(CHECKS), assertion_count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
