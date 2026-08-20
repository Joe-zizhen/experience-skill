# 通用经验（跨项目）

> 规则与项目经验相同：四问准入（会重现/重导有代价/改变行动/带死因）、祈使句、标题=触发条件+关键词簇；失效标"疑似失效"走人工问询；入库/移除/冷藏均经用户确认。
> 规模：单文件全平铺（≤150 条）；超过则拆为 `general/` 目录分级，规则同项目侧。
> 项目特定经验不进本文件，去项目 `docs/experience/`。

## [Windows/Git Bash] 在 Git Bash 里给原生命令传路径前

- 行动：传 Windows 路径给原生命令（adb、java 等）时加 `MSYS_NO_PATHCONV=1` 前缀，防 Git Bash 把 `/` 开头参数自动转路径；项目路径含中文时，把构建工具的 `TMP`/`TEMP`/`GRADLE_USER_HOME` 显式重定向到项目内或纯 ASCII 路径。
- 根因：Git Bash 的 MSYS 路径转换与 JVM/构建工具对中文临时目录的兼容问题。
- 死因：迁移到原生 Windows 终端或 WSL 后。

## [Android 真机] adb 自动化输入与装机前

- 行动：`input text` 无法注入中文（NPE），验收文本用拼音/数字；设备序列号随设备池变化，先 `adb devices` 确认再拼命令。
- 死因：更换自动化输入方案（如 UI Automator 注入）后复核。

## [Kimi Code/hook] 在 Windows 上配置任何 hook 时

- 行动：`command` 必须用绝对路径字面量（`~` 不被展开，hook 静默失败）；配置后加 `echo` 探针日志区分"未触发"与"执行失败"；推广原则——任何 fail-open 静默机制都必须自带观测手段（日志），否则"没生效"和"生效了但看不见"无法区分。
- 根因：Windows cmd 不做 `~` 展开 + hook fail-open 设计吞掉全部错误。
- 证据：2026-08-19 实测，两轮排查（探针 hook-fired.log + 执行日志 experience-hook.log）定位，改绝对路径后 `result=injected`。
- 死因：Kimi 官方修复 `~` 展开或文档明确 Windows 行为后。
- 记录：2026-08-19｜最近命中：2026-08-19

## [Context7/MCP] 用 Context7 查库文档前

- 行动：当已选定某个库、需要其最新文档/API 用法时，直接让 agent 用 Context7 拉取（提示词加 "use context7" 或指定库 ID，如 /squareup/retrofit）；它不回答"有没有这样的库"，不适用于选型——选型走 Web 搜索/GitHub/包注册表。免费档 1000 次调用/月、按月重置，resolve-library-id 与 query-docs 每次调用均计次。
- 根因：Context7 是文档分发服务而非包注册表——检索只在已收录库内做名字匹配，覆盖与排序不足以支撑选型决策。
- 证据：2026-08-19 实测官方定价页（context7.com/plans）与仓库 README（github.com/upstash/context7）。
- 死因：Context7 服务停用或计费规则变更后。
- 记录：2026-08-19｜最近命中：2026-08-19

## [网络/GitHub] git push 失败但 gh api 通时（push 超时、TLS 中断、schannel、443、推送不了、推不上去）

- 行动：当 git push GitHub 反复失败（TLS 中断/443 超时）但 `gh api` 正常时，改走 git data API 推送：建 tree（带文件 content）→ 建 commit → PATCH refs/heads/main 指向新提交；内容与本地提交一致但 SHA 为服务端新建，网络恢复后用 `git fetch origin && git reset --hard origin/main` 对齐本地（本地重复提交可弃）。
- 根因：github.com（git 协议）与 api.github.com 被网络层区别对待，前者被干扰时后者仍可用（推断，与"两次 push 失败而 gh api 秒回"实测一致）。
- 证据：2026-08-20 实测 git push 两次失败（schannel 中断 + 443 连接超时），`gh api` 正常；改走 git data API 一次推送成功（Joe-zizhen/experience-skill，远端提交 5f043cac）。
- 死因：网络环境变化（github.com 直连长期稳定）后复核。
- 记录：2026-08-20｜最近命中：2026-08-20
