# 题集（tickets）

仿 [ponytail](https://github.com/DietrichGebert/ponytail) `benchmarks/agentic/tasks.py` 的一句话工单风格（MIT）：
其中 t01–t06 直接采用其后端工单原文（被改对象从 full-stack-fastapi-template 换成本仓 mini fixture），
t07–t08 为本仓自拟。所有工单故意「一句话」，把「要做什么」说清、把「怎么做」留给执行器——正是容易诱发过度工程的形态。

## LOC 轴（8 张）

| id | ticket 原文 | 出处 |
|---|---|---|
| t01-duplicate | Add an endpoint to duplicate an item. | ponytail tmpl-be-duplicate |
| t02-search | Add an endpoint to search items by title. | ponytail tmpl-be-search |
| t03-count | Add an endpoint that returns how many items the current user has. | ponytail tmpl-be-count |
| t04-archive | Add the ability to archive and unarchive an item. | ponytail tmpl-be-archive |
| t05-bulkdelete | Add an endpoint to delete several items at once. | ponytail tmpl-be-bulkdelete |
| t06-csv | Add an endpoint to export the current user's items as CSV. | ponytail tmpl-be-csv |
| t07-retry | Make webhook delivery in app/services.py retry when the remote server fails. | 本仓自拟 |
| t08-health | Extend the health endpoint to also report whether the database is reachable. | 本仓自拟 |

## 实验臂（arms）

仿 ponytail 的四臂设计取三臂（caveman 轴测「话少」而非「代码少」，不取）：

| arm | 注入内容 | 回答什么 |
|---|---|---|
| `base` | 无纪律文本，显式禁用一切 skill | 同一个 agent 裸跑什么样 |
| `yagni` | 一句话 "Follow YAGNI principles, and prefer one-liner solutions." | 一句话 prompt 够不够（issue #126 之问） |
| `skill` | Read 工具读 lean-engineer/SKILL.md 全文并遵守 | 完整纪律值多少 |

## 并发/幂等轴（c1–c4，第二批扩题）

目的：压 skill 现在盖不住的失败类别。安全要求隐含在措辞里（"caller retries"、"many workers call this at the same time"），
打分器用 Barrier 制造确定性竞争 + 逐轮不变量判定（恰好一次 / 不超卖 / 金额守恒）。

| id | 题面要点 | 埋的雷 |
|---|---|---|
| c1-idempotent-charge | `charge(conn, order_id, amount)`，调用方超时会重试 | 裸 INSERT = 重试双扣；先查后插 = 并发双扣 |
| c2-stock-race | `buy(conn, item_id, n)`，多 worker 同时调 | 先查后改 = 超卖 |
| c3-double-register | `register(conn, email)`，浏览器双击/重试 | 检查再插 = 双注册 |
| c4-transfer | `transfer(conn, from, to, amount)`，并发负载 | 读改写丢更新 = 金额不守恒 |

打分器环境：WAL 文件库 + busy timeout；每线程一条新连接，连接生命周期归打分器（用完 rollback+close）。

## 口径

- 每 cell 独立目录副本（runner.py setup），互不共享上下文；subagent 零上下文启动
- 三臂同一模型、同一 wrapper 话术，唯一差异是纪律注入
- LOC = git diff 新增行，代码与测试分记；原 16 条测试须全绿且原测试文件未改 = original_suite_green
- 新依赖看 requirements.txt diff
- pilot：8 工单 × 3 臂 × n=1 = 24 cell；样本量不足以谈分布，只看方向性信号
- 正式：LOC 轴 n=4（96 cell）+ safety 轴 n=4（72 cell）+ 并发/幂等轴 n=4（48 cell），safety/并发判定见 `safety/tasks.py`（确定性打分器，先 selftest 再跑分）
