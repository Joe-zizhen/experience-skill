# mymodules 各技术栈装配配方

**[DEFAULT]**

识别信号 → 判定 → 落点目录（code_location）→ 接线 → 验证命令。
表中未覆盖的栈：按同构原则找该栈的「目录 + 导入」机制处理；仍不确定就问用户，把答案钉进 `docs/power.md` 的 CONFIG 区。

## 使用时机（硬门禁）[INV]

本配方只在实现后已出现真实入库候选且入库三问首次全部答“是”时使用。首次触发 mymodules、尚无入库候选或三问任一不为“是”时，不许运行这里的创建/接线命令，也不许创建目录或 `docs/power.md`（经缺口表问询同意的播种不在此列）。触发时必须先记录延迟装配原因、时间、候选能力和三问原始结论。

## 模型（所有栈统一）

`mymodules` 是一个**目录**，不是包/模块工程：每个可复用能力封装成目录里一个独立文件，业务代码按索引条目入口从对应文件 import（前端可经 `index.ts` 统一出口）。不为它新建 Gradle 模块、npm workspace 包、cargo crate 或 classlib——那是过度工程。

## 识别表 [DEFAULT]

下表给出技术栈对应的候选落点目录，不是见到信号就自动新建的指令。选定 `code_location` 前先搜索现有领域/基础设施边界；对 `common|shared|core|base|util(s)|lib` 候选运行 grep/rg 导入或调用计数，保存命令和输出，证明其中现有内容已被两个以上独立位置真实复用。没有该证据时，不得仅凭目录名选中候选；优先按能力所属领域/基础设施边界放置，仍有两个以上合理答案时问用户一次并钉进 `docs/power.md` 的 CONFIG 区。

| 信号文件/特征 | 判定 | 落点目录（code_location） |
| --- | --- | --- |
| `settings.gradle(.kts)` + 模块用 `com.android.*` 插件 | Android | 现有 shared/领域目录优先；没有再问用户；无现成边界时的候选为使用方模块源码集内的 `mymodules/` 包目录 |
| `settings.gradle(.kts)` / `pom.xml`，无 Android 插件 | JVM 后端/库 | 现有 shared/领域目录优先；没有再问用户；候选为使用方模块 `src/main/java/<pkg>/mymodules/`（或对应 kotlin 源码目录） |
| `package.json` 有 `workspaces`（或 pnpm-workspace.yaml） | 前端/Node monorepo | 现有 shared/领域目录优先；没有再问用户；候选为使用方包内 `src/mymodules/` |
| `package.json` 无 workspaces，含 vue/react/next/svelte 等 | 单体前端 | 现有 shared/领域目录优先；没有再问用户；候选为 `src/mymodules/`（目录+别名） |
| `package.json` 为纯后端（express/koa/nestjs 等） | Node 后端 | 现有 shared/领域目录优先；没有再问用户；候选为 `src/mymodules/` |
| `go.mod` | Go | 现有 `internal/` 领域目录优先；没有再问用户；候选为 `internal/mymodules/` |
| `pyproject.toml` / `requirements.txt` / `setup.py` | Python | 现有包/领域目录优先；没有再问用户；候选为 `mymodules/` |
| `Cargo.toml`（含 `[workspace]`） | Rust | 现有领域模块目录优先；没有再问用户；候选为使用方 crate 的 `src/mymodules/` |
| `*.sln` / `*.csproj` | .NET | 现有 shared/领域文件夹优先；没有再问用户；候选为现有项目内 `mymodules/` 文件夹 |
| 全部不命中 / 多栈混合仓库 | 未知/混合 | 问用户；多栈仓库按子项目分别钉进 `docs/power.md` 的 CONFIG 区 |

## Android (Gradle)

- 信号：根 `settings.gradle(.kts)`，且任一模块应用 `com.android.application` 或 `com.android.library` 插件。
- 创建：使用方模块源码集内新建包目录，如 `app/src/main/java/<pkg>/mymodules/`；每个能力一个 Kotlin/Java 文件。
- 接线：无需接线（同模块源码集），业务代码按包名 import。
- 验证：使用方模块 assemble（如 `./gradlew :app:assembleDebug`）绿。

## JVM 后端/库 (Gradle/Maven)

- 创建：使用方模块 `src/main/java/<pkg>/mymodules/`（或对应 kotlin 源码目录），每个能力一个类文件。
- 接线：无需接线，按包名 import。
- 验证：`./gradlew build` 或 `mvn compile` 通过。

## 前端/Node monorepo (workspaces)

- 创建：使用方包内 `src/mymodules/` 目录，每个能力一个文件，`index.ts` 统一出口。不动根 workspaces、不新建包。
- 接线：包内相对导入或该包已有别名。
- 验证：使用方 `tsc --noEmit` / `npm run build` 通过。

## 单体前端 / Node 后端（无 workspaces）

- 创建：`src/mymodules/` 目录，每个能力一个文件，`index.ts` 统一出口。
- 接线：配路径别名（`tsconfig.json` 的 `paths`、vite/webpack alias）；业务代码统一从 `mymodules` 的 index 导入（index 只是出口，每个能力的本体各居其文件）。
- 验证：`tsc --noEmit` 或 `npm run build` 通过。
- 注意：小项目不升级为 workspace 包，目录 + 约定即可，避免过度工程。

## Go

- 创建：`internal/mymodules/` 目录，按能力分文件；`internal` 天然阻止外部仓库导入。
- 验证：`go build ./...` 与 `go vet ./...` 通过。

## Python

- 创建：`mymodules/` 目录含 `__init__.py`（或 src 布局下的目录），按能力分模块文件。
- 验证：`python -c "import mymodules"` 通过；有测试则 `pytest` 绿。

## Rust

- 创建：使用方 crate 内 `src/mymodules/` 目录 + `mod.rs`（或 `src/mymodules.rs`），每个能力一个子文件；不 `cargo new` 新 crate。
- 接线：`lib.rs` / `main.rs` 加 `mod mymodules;`（需对 crate 外暴露时 `pub mod mymodules;`）。
- 验证：`cargo build` 通过。

## .NET

- 创建：现有项目内 `mymodules/` 文件夹，每个能力一个 `.cs` 文件（SDK 风格 csproj 默认 glob 包含，无需改工程文件）。
- 验证：`dotnet build` 通过。

## 通用收尾（所有栈）

1. 验证命令通过后，把装配事实钉进 `docs/power.md` 顶部 CONFIG 区：stack、code_location、pinned_at、detection_evidence。
2. 在 `docs/power.md` 登记触发装配的真实候选（索引条目含契约要素：是什么 / 解决什么 / 何时用 / 何时别用 / 入口（import 路径）/ 示例 / 依赖）；结束时不得留下空目录或空索引。
3. 治理挂钩：AGENTS.md 有则续写必读路由、无则新建最小版（只含 mymodules 路由与复用调研约定，不编造其他项目信息；**新建或改写 AGENTS.md 前同样先问用户**，与 power.md 播种同走缺口问询）；项目已有计划模板则加入「复用调研」必填段，无模板则并入 AGENTS.md 一条规则，不单独建文件。
