# Myskills — 个人 AI agent skill 集合

核心是两个相辅相成的 skill：

| skill | 职责 |
| --- | --- |
| `experience/` | 外置大脑（跨会话记忆）：坑、入口、用户决策、功能经验的固化与检索；门禁 + hook 注入 + 自清洁 |
| `senior-engineer/` | 编码时的一切：六条编码红线、六条行为铁律、复用检索与 mymodules 入库治理、对抗性审查 |

连通性：senior-engineer 入库可复用模块 → experience 记功能经验；experience 命中功能经验 → 回 mymodules 核实后复用。

独立工具 skill：

| skill | 职责 |
| --- | --- |
| `systematic-debugging/` | 系统化调试方法论：先根因后修复；读全报错 → 固定复现 → 组件边界插桩 → 单假设最小验证（源自 obra/superpowers，MIT；已删除自行加入的 Loop 交接模式） |
| `5w-ledger-v1-2/` | 证据准入台账式 5W 根因分析：事故级 / 多因交织 / 跨时间窗 / 审计交接场景用，日常 bug 不用 |
| `first-principle-v2/` | 第一性原理方案设计：重大、难逆、假设未决的决策，从基础事实推导最简正解 |

## 安装（Kimi Code）

```bash
git clone https://github.com/Joe-zizhen/experience-skill.git ~/skills-collection
cp -r ~/skills-collection/experience ~/.agents/skills/
cp -r ~/skills-collection/senior-engineer ~/.agents/skills/
cp -r ~/skills-collection/systematic-debugging ~/.agents/skills/
cp -r ~/skills-collection/5w-ledger-v1-2 ~/.agents/skills/
cp -r ~/skills-collection/first-principle-v2 ~/.agents/skills/
```

Claude Code 则拷到 `~/.claude/skills/`。

## 同步

- 本仓是 skill 的唯一权威源：在本地 skill 目录改完后，拷回对应子目录，commit + push。
- 各项目里的 `docs/experience/`（项目经验）不进本仓，随项目自己的 git 走。
