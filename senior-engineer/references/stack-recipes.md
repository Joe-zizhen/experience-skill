# mymodules 各技术栈装配配方

**[DEFAULT]**

识别信号 → 判定 → 隔离单元（code_location）→ 接线 → 验证命令。
表中未覆盖的栈：按同构原则找该栈的"库/包"机制处理；仍不确定就问用户，把答案钉进 CONFIG.md。

## 使用时机（硬门禁）[INV]

本配方只在实现后已出现真实入库候选且入库三问首次全部答“是”时使用。首次触发 mymodules、尚无入库候选或三问任一不为“是”时，不许运行这里的创建/接线命令，也不许创建包、模块、`CONFIG.md`、`INDEX.md` 或模板。触发时必须先记录延迟装配原因、时间、候选能力和三问原始结论。

## 识别表 [DEFAULT]

下表给出技术栈对应的候选隔离单元，不是见到信号就自动新建的指令。选定 `code_location` 前先搜索现有领域/基础设施边界；对 `common|shared|core|base|util(s)|lib` 候选运行 grep/rg 导入或调用计数，保存命令和输出，证明其中现有内容已被两个以上独立位置真实复用。没有该证据时，不得仅凭目录名选中候选；优先按能力所属领域/基础设施边界放置，仍有两个以上合理答案时问用户一次并钉进 CONFIG。

| 信号文件/特征 | 判定 | 隔离单元（code_location） |
| --- | --- | --- |
| `settings.gradle(.kts)` + 模块用 `com.android.*` 插件 | Android | 新建 `:mymodules` library 模块 |
| `settings.gradle(.kts)` / `pom.xml`，无 Android 插件 | JVM 后端/库 | 新建 `mymodules` 子模块（Gradle module / Maven module） |
| `package.json` 有 `workspaces`（或 pnpm-workspace.yaml） | 前端/Node monorepo | 新建 `packages/mymodules` workspace 包 |
| `package.json` 无 workspaces，含 vue/react/next/svelte 等 | 单体前端 | `src/mymodules/` 目录 + 路径别名 + 导入边界约定 |
| `package.json` 为纯后端（express/koa/nestjs 等） | Node 后端 | `src/mymodules/` 目录 + 导入边界约定 |
| `go.mod` | Go | `internal/mymodules/` 包（天然隔离） |
| `pyproject.toml` / `requirements.txt` / `setup.py` | Python | `mymodules/` 包目录（含 `__init__.py`） |
| `Cargo.toml`（含 `[workspace]`） | Rust | 新建 workspace crate `mymodules` |
| `*.sln` / `*.csproj` | .NET | 新建 class library 项目 `mymodules` 并加入解决方案 |
| 全部不命中 / 多栈混合仓库 | 未知/混合 | 问用户；多栈仓库按子项目分别钉 CONFIG |

## Android (Gradle)

- 信号：根 `settings.gradle(.kts)`，且任一模块应用 `com.android.application` 或 `com.android.library` 插件。
- 创建：根目录新建 `mymodules/`，含 `build.gradle`（`com.android.library` + kotlin 插件，`namespace` 自取，`compileSdk`/`minSdk` 对齐根工程）与 `src/main/AndroidManifest.xml`（空 manifest）。
- 接线：`settings.gradle` 加 `include ':mymodules'`；使用方模块 `dependencies` 加 `implementation project(':mymodules')`。
- 验证：`./gradlew :mymodules:help` 成功即接线通过；有代码后 `:mymodules:assembleDebug` 要绿。

## JVM 后端/库 (Gradle/Maven)

- Gradle：`settings.gradle` 加 `include ':mymodules'`，模块用 `java` 或 `org.jetbrains.kotlin.jvm` 插件；使用方 `implementation project(':mymodules')`。
- Maven：父 pom 加 `<module>mymodules</module>`，使用方加 dependency。
- 验证：`./gradlew :mymodules:build` 或 `mvn -pl mymodules compile`。

## 前端/Node monorepo (workspaces)

- 创建：`packages/mymodules/`，含 `package.json`（name 如 `@<scope>/mymodules`）与 `src/index.ts` 统一出口。
- 接线：根 `package.json` workspaces 覆盖 `packages/*`（通常已有）；使用方 `dependencies` 加 `"@<scope>/mymodules": "workspace:*"`（pnpm）或 `"*"`（npm/yarn）。
- 验证：根目录 install 后，使用方 `import` 一个空导出并 `tsc --noEmit` / `npm run build` 通过。

## 单体前端 / Node 后端（无 workspaces）

- 创建：`src/mymodules/` 目录，内含 `index.ts`（统一出口）；每个能力一个子目录/文件。
- 接线：配路径别名（`tsconfig.json` 的 `paths`、vite/webpack alias）；约定业务代码只能从 `mymodules` 的 index 导入。
- 验证：`tsc --noEmit` 或 `npm run build` 通过。
- 注意：小项目不升级为 workspace 包，目录 + 约定即可，避免过度工程。

## Go

- 创建：`internal/mymodules/` 包，按能力分子文件；`internal` 天然阻止外部仓库导入。
- 验证：`go build ./...` 与 `go vet ./...` 通过。

## Python

- 创建：`mymodules/` 目录含 `__init__.py`（或 src 布局下的子包），按能力分模块文件。
- 验证：`python -c "import mymodules"` 通过；有测试则 `pytest` 绿。

## Rust

- 创建：`cargo new mymodules --lib`，根 `Cargo.toml` `[workspace].members` 加 `mymodules`；使用方 `[dependencies] mymodules = { path = "../mymodules" }`。
- 验证：`cargo build` 通过。

## .NET

- 创建：`dotnet new classlib -n mymodules`，`dotnet sln add mymodules`；使用方 `dotnet add reference mymodules`。
- 验证：`dotnet build` 通过。

## 通用收尾（所有栈）

1. 验证命令通过后，写 `docs/mymodules/CONFIG.md`：stack、code_location、catalog、pinned_at、detection_evidence。
2. 写 `docs/mymodules/INDEX.md` 与 `docs/mymodules/entries/_template.md`，并在同一流程登记触发装配的真实候选；结束时不得留下空包或空目录表。
3. 治理挂钩：AGENTS.md 有则续写必读路由、无则新建最小版（只含 mymodules 路由与复用调研约定，不编造其他项目信息）；项目已有计划模板则加入「复用调研」必填段，无模板则并入 AGENTS.md 一条规则，不单独建文件。
