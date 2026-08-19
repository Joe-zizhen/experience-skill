# Myskills — 个人 AI agent skill 集合

两个相辅相成的 skill：

| skill | 职责 |
| --- | --- |
| `experience/` | 外置大脑（跨会话记忆）：坑、入口、用户决策、功能经验的固化与检索；门禁 + hook 注入 + 自清洁 |
| `senior-engineer/` | 编码时的一切：六条编码红线、六条行为铁律、复用检索与 mymodules 入库治理、对抗性审查 |

连通性：senior-engineer 入库可复用模块 → experience 记功能经验；experience 命中功能经验 → 回 mymodules 核实后复用。

## 安装（Kimi Code）

```bash
git clone https://github.com/Joe-zizhen/experience-skill.git ~/skills-collection
cp -r ~/skills-collection/experience ~/.agents/skills/
cp -r ~/skills-collection/senior-engineer ~/.agents/skills/
```

Claude Code 则拷到 `~/.claude/skills/`。

## 同步

- 本仓是 skill 的唯一权威源：在本地 skill 目录改完后，拷回对应子目录，commit + push。
- 各项目里的 `docs/experience/`（项目经验）不进本仓，随项目自己的 git 走。
