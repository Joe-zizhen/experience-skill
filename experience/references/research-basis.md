# 研究依据与本包采用的机制

## 证据与设计的关系 [DEFAULT]

本包目标是让后续工程任务更容易正确完成。以下一手资料提供机制线索和评测方法；其中 Anthropic 为工程案例，论文各有独立系统与实验设置。组合成当前 Markdown Wiki 是面向用户目标的工程选择，需用本包真实任务验证，不能当作有效性或最优性的证明。

在线/离线描述处理时机；现场、笔记、主题 Wiki、目录与当前上下文描述知识表示和使用位置。这两个维度分别处理。

## 机制映射 [DEFAULT]

以下题名、链接和所述内容于 2026-11-08 直接核对发布方页面或论文；版本固定用于追溯，后续更新需重新核验。只保留与本次规则有直接关系的来源。

| 一手资料 | 核实的结论或观察 | 本包采用及限制 |
|---|---|---|
| Lance Martin / Anthropic，[The components of agent memory](https://www.anthropic.com/research/components-of-agent-memory)，2026-11-06 | 文中用原始会话纠正错误笔记；内部语料的 Wiki 加搜索比单用 Wiki 更有效；也出现 Wiki 无明显收益、比原文更大和并发写共享页遗漏条款的案例 | 回源纠错、增量主题和导航、协调写入，检索不足仍查原始来源。特定模型/数据与小型问题集的结果不证明本 Wiki 有效；文中对持续全量维护的成本也保留疑问 |
| Kevin Lin 等，[Sleep-time Compute: Beyond Inference Scaling at Test-time](https://arxiv.org/abs/2504.13171v1)，2025-04-17；[全文](https://arxiv.org/html/2504.13171v1) §5.4、§6–7 | 提前处理共享上下文可摊薄后续查询计算；收益依赖未来查询的可预测性。SWE-Features 的高在线预算条件下，纯在线方案更好 | 选择实际重复需求、有界独立批次，比较维护加使用的总成本。论文离线计算不等于 Markdown 自带调度，也不保证每次巩固都划算 |
| Di Wu 等，[LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory](https://arxiv.org/abs/2410.10813v2)，2025-03-04；[全文](https://arxiv.org/html/2410.10813v2) §3–4、附录 E.5 | 评估提取、跨会话/时间推理、知识更新与信息不足时拒答；错误分析包含正确检索但错误生成 | 分开看保存覆盖、固定预算召回与应用，使用独立任务所需证据集。对话问答不是工程行动；不机械要求召回任务不需要的旧事实 |
| Zexue He 等，[MemoryArena: Benchmarking Agent Memory in Interdependent Multi-Session Agentic Tasks](https://arxiv.org/abs/2602.16313v2)，2026-09-17；[全文](https://arxiv.org/html/2602.16313v2) 摘要、附录 C.3 | 以相互依赖的跨会话行动检验记忆；对话记忆表现好不保证行动任务表现好，完整上下文等对照仍有失败 | 测下一次实际定位、决策和行动结果，分别归因于读取、理解、应用或其他因素。不能用引用次数代替结果，也不能据该基准外推本包收益 |
| Qizheng Zhang 等，[Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models](https://arxiv.org/abs/2510.04618v3)，2026-03-29；[全文](https://arxiv.org/html/2510.04618v3) §2–3 | 讨论过度压缩与反复整篇重写引起的信息丢失，采用局部增量和整理机制 | 保留条件/例外并局部更新。这里只借鉴原则，没有实现 ACE 的角色流水线、确定性合并及反馈算法，不继承其性能结论或取消读取预算 |
| Tianyu Gao 等，[Enabling Large Language Models to Generate Text with Citations](https://arxiv.org/abs/2305.14627v2)，2023-10-31，ALCE | 将答案正确性、引用支持与覆盖等质量分别评价 | 逐项核对来源是否支持主张，保留推导身份。出现链接并不证明结论真实；该研究不验证本包的溯源规则已被执行 |
| Zhaorun Chen 等，[AgentPoison: Red-teaming LLM Agents via Poisoning Memory or Knowledge Bases](https://arxiv.org/abs/2407.12784v1)，2024-07-17；[全文](https://arxiv.org/html/2407.12784v1) §3.2、Limitations | 可写入检索数据库的攻击者利用污染条目影响代理；攻击设计涉及 embedding 模型与优化触发器 | 将资料当证据、核对授权来源、限制持久化范围并隔离未通过更新。其攻击成功率不能套到文本检索；纯文本也不能据此被宣称免疫污染 |

## 为什么提供独立巩固模式 [DEFAULT]

实际工作中有些更新可以在取得证据后局部完成；跨案例对照、冲突核验和知识重组需要集中处理多个材料。本包让同一维护流程既能随任务运行，也能在明确范围内独立运行。选择的依据是工作目标和证据范围，而非“恰好两层”的预设。

独立巩固产出当前认识、依据、适用边界、知识联系与验证结果。必要现场优先引用现有任务产物；保存最小片段是本包为保真和后续可用性作出的工程安排，文件扩展名不是论文标准。

## 治理与实现选择 [DEFAULT]

新增主张、既有纠错、表示重组和范围提升分别判断，是根据用户少打断、保真和正确更新的目标作出的治理设计。现有主题的纠错沿用其用途，新增内容仍独立评估；具体内容、批次或可撤销的持续维护约定控制保存范围；在有效预授权内自主验收保存，以一次简报降低打扰。该授权模型与默认预算是本包的工程选择，论文没有证明它们最佳。

## 本包的验证范围 [DEFAULT]

工具检查与测试只覆盖所检查的格式、路径、单调用预算和只读行为；新上下文行为验证检查规则是否执行；维护前后与真实项目对照检查任务收益。这三类证据分别报告，本轮仅文档修订不产生新的行为或收益分数。

本包使用 Markdown、文本检索、显式链接和当前宿主理解能力。研究中的参数训练、向量模型、图数据库、独立服务与自动情感打分不进入实现范围。
