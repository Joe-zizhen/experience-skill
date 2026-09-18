# Myskills — 个人 AI agent skill 套件

八个独立插件，给会把「看起来做完了」当目标的执行器（Claude Code、Codex 等）用。可只用一个，可搭配。**没有必须走完的流水线，也没有开机 skill。**

谁在什么场合用、定律原文、闭清单死因，以 [`contracts/suite-v1.yaml`](contracts/suite-v1.yaml) 为权威。本 README 是给人看的说明书，不是第二份规则。

---

## 1. 这是什么

每个插件管一种不确定：

| 不确定 | 插件 |
| --- | --- |
| 还没想清要什么 | `pm` |
| 这次改动落在哪 | `architect` |
| 代码该怎么写 | `senior-engineer` |
| 根因还没定 | `systematic-debugging` |
| 事故要复盘 | `5w-ledger-v1-3` |
| 选项被类比塌缩 | `first-principle-v2` |
| 付过的代价下次还要付 | `experience`（后台检索，不当主驱动） |
| 输出停在不会错的中间值 | `excellence`（手动点名） |

**不是：** 一条「需求 → 架构 → 编码 → 复盘」流水线；也不是第七个开机 skill。安装器写入宿主入口的是 [`contracts/boot.md`](contracts/boot.md)，只是认人条。

对得上谁就用谁。用错了：停下，说出证据，换一个。

---

## 2. 定律

**不可信执行器会把「看起来做完了」当目标。** 只许闭清单认形（不准估）、格子能核对、留下去的先问人、做成看现实。自评、散文充证据、没同意就写、没看见就声称完成——都算没做。

权威文本在 `contracts/suite-v1.yaml` 的 `law`。立刻能用的推论：认形只对闭清单；硬门槛只要命令+命中/未命中；装东西、改配置、播种、删数据先问；做成看现实，不看文档写完或测试变绿；存储不是经验——不进窗口等于没有。

规则四级：`[INV]` 违反即缺陷；`[DEFAULT]` 可覆盖；`[HEURISTIC]` 只触发复核；`[EXAMPLE]` 无规范效力。绝对化词语只许活在 `[INV]`。

skill 正文只写自己交付什么。点名别的插件只许出现在「可选连通」。互斥句（这不是某某、某某归某某管）不准写。认人只活在开机卡和 suite 合同。

---

## 3. 怎么认人

安装后，宿主入口里会有开机卡。这一单对得上谁，就用谁：

| 你的情况 | 用哪个 |
| --- | --- |
| 还在想要什么、要写需求或任务书 | `pm` |
| 要找落点、要类图/时序、要动模块归属 | `architect` |
| 已经在写、改、审代码 | `senior-engineer` |
| 坏了、测不过、行为不对，根因还没定 | `systematic-debugging` |
| 事故、多因、要复盘或交接 | `5w-ledger-v1-3` |
| 选项集像是被类比塌缩、或明确要第一性原理 | `first-principle-v2` |
| 项目入口已挂短契约 | `experience` 后台只读；不要当开工仪式 |
| 开放题（方案/文案/观点/架构权衡）要优秀不要及格 | `excellence`（手动点名才启动） |

仅「难回头 / 重大」不够当第一性原理。同一时刻一个主插件即可。只读经验检索和已挂短契约的架构总账是背景层，不算主驱动。编码任务以 `senior-engineer` 为主驱动，底图靠短契约进窗口。

---

## 4. 八个插件（各管什么）

### `pm`

把想法熬成可验收的需求规格。对人说大白话。需求阶段零动手。规格点头后本 skill 停。

### `architect`

给这次改动找落点。交付结构，不是代码。

- 底图只登记**现状**；意图只活在尚未落地的本单图纸。
- `docs/architect/INDEX.md` 是总账，不是细架构。细的（拥有 + 进出边 + 不拥有）在详情文件。
- 格子能核对：点名的类型必须能搜到，或标「新造（已搜未命中）」。命中 INDEX 行必须搜该行符号。
- 播种分三批（方法，不写死某项目名单）：入口与一跳 → 主玩法（全表进出边）→ 其余（薄细：拥有 + 至少一边 + 不拥有）。每批 ≤15 行，INDEX ≤40 行。
- 编码不切本插件为主驱动。没挂短契约必须写明：底图不会被自动读到。

### `senior-engineer`

写、改、审代码。先对大改闭清单认形，不准估小改。测试绿不能单独当做成。项目已挂架构短契约则编码前扫 INDEX，命中行搜符号。

### `systematic-debugging`

技术故障的因果调查。没有足以选修复边界的解释，不做永久修复。止血不是修复。查着不是技术故障：停下，说出证据，本单交付到此为止。

### `5w-ledger-v1-3`

事故级、多因、审计复盘。证据台账 ADMIT / REFUTED / UNRESOLVED。日常局部 bug 不用它。

### `first-principle-v2`

选项集被类比塌缩时用。钉对象 → 拆零件 → 独立评估 → 缺口 → 再组装。默认停在设计。没有授权不准实现。

### `experience`

跨会话例外清单。项目入口短契约每任务读 INDEX；本体只在写入、维护、显式检索、播种时调用。入库四问：会重现、重导有代价、改变行动、写得出失效条件。人工闸门。代码赢。

### `excellence`

开放性任务的卓越输出工作流，手动点名才启动。定标 → 排平庸 → 发散 → 收敛 → 批评，成品置顶、过程为附录。事实问答、修 bug、明确指令的执行类任务不启动。效果与实测证据见 [`excellence/README.md`](excellence/README.md)。

---

## 5. 仓库结构

```
experience-skill/
├── contracts/
│   ├── suite-v1.yaml
│   ├── boot.md
│   └── dark-cases.md
├── pm/
├── architect/
├── senior-engineer/
├── systematic-debugging/
├── 5w-ledger-v1-3/
├── first-principle-v2/
├── experience/
├── excellence/
├── tools/
│   ├── install.py
│   ├── check-suite.py
│   └── publish.sh
├── LICENSE
└── README.md
```

每个插件至少有 `SKILL.md` 和 `agents/openai.yaml`。不要把整仓拷进宿主 skills 目录——走安装器，只装这八个目录 + 开机卡。

项目里的 `docs/experience/`、`docs/architect/` 不进本仓。

---

## 6. 安装

```bash
git clone https://github.com/Joe-zizhen/experience-skill.git ~/skills-collection
python ~/skills-collection/tools/install.py --source ~/skills-collection --host-dir ~/.agents/skills
```

| 宿主 | `--host-dir` | 开机卡 |
| --- | --- | --- |
| Codex / `.agents` | `~/.agents/skills` | `~/.agents/AGENTS.md` |
| Claude Code | `~/.claude/skills` | `~/.claude/CLAUDE.md` |

装完重启宿主。技能清单是启动缓存。

安装器：暂存 → 校验 → 备份 → 原子替换 → 读回哈希，失败回滚。`--skills` 可只装几个。`--verify-only` / `--dry-run` 可用。

技能仓改完未安装 = 没做（存储不是经验）。日常改活副本 `~/.agents/skills` 时，可用 junction 把 `.claude/skills` 指过去。

---

## 7. 校验与发布

提交前：

```bash
python tools/check-suite.py
```

检查 frontmatter、绝对词越级、可选连通外点名其他插件、UTF-8、开机卡 / README / suite 定律。退出码 0 = 全过。

暗卷见 [`contracts/dark-cases.md`](contracts/dark-cases.md)。纸面不算过。

把活副本拍回本仓会覆盖仓库，必须显式确认：

```bash
bash tools/publish.sh --from-live
git add -A && git commit && git push
```

无 `--from-live` 会拒绝。commit + push 仍由人决定。

---

## 8. 常见误用

| 误用 | 该怎样 |
| --- | --- |
| 八个插件当流水线每单走一遍 | 对得上谁用谁 |
| `experience` 当开工仪式 | 短契约后台检索 |
| 仅因为难回头就套第一性原理 | 看选项是不是被类比塌缩 |
| 改按钮文案却画全仓类图 | 读底图总账即可，不改底图 |
| 把细架构写进 INDEX | 总账一行一个模块；边在详情里 |
| 填满格子 / 测绿就声称完成 | 做成看现实 |
| 技能仓改完未安装 | 窗口里看不见 = 没做 |
