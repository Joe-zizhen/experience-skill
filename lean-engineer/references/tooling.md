# 各语言质量门工具速查

按关卡分组。优先使用项目已有配置；以下为各生态主流选择，安装前先在 manifest / lockfile 中确认是否已存在。安装任何工具前先按「缺口必问」征得用户同意。

## JavaScript / TypeScript

| 关卡 | 工具 | 典型命令 / 配置 |
|---|---|---|
| 复杂度 | ESLint `complexity` 规则（需项目已有 eslint 配置；ESLint 9 起无配置文件会直接报错，先 `npm init @eslint/config` 创建） | `eslint --rule '{"complexity":["error",10]}' src/` |
| 测试+覆盖率 | vitest / jest（自带 coverage） | `vitest run --coverage` |
| 变异测试 | Stryker（支持原生增量模式） | `npx stryker run`（增量：`--incremental`） |
| 架构约束 | dependency-cruiser；eslint-plugin-boundaries；madge（循环依赖） | `depcruise src --validate .dependency-cruiser.js`；`madge --circular src/` |

## Python

| 关卡 | 工具 | 典型命令 |
|---|---|---|
| 复杂度 | radon（`cc`）、xenon（门禁式）、lizard | `radon cc src -a -nb`；`xenon --max-absolute B src/` |
| 测试+覆盖率 | pytest + coverage.py | `pytest --cov=src --cov-fail-under=80` |
| 变异测试 | mutmut、cosmic-ray（无原生增量开关，按文件/模块分批运行控制成本） | `mutmut run && mutmut results` |
| 架构约束 | import-linter（分层契约，门禁用它）；pydeps 只是依赖图可视化工具，循环依赖只在图里高亮，不能充当门禁 | `lint-imports` |

## Java / Kotlin

| 关卡 | 工具 | 典型命令 |
|---|---|---|
| 复杂度 | SonarQube / SonarLint；PMD；Checkstyle（CyclomaticComplexity） | `mvn sonar:sonar` 或 PMD ruleset |
| 测试+覆盖率 | JUnit + JaCoCo | `mvn test jacoco:report` |
| 变异测试 | PIT (PITest)（无增量开关，用 `-DtargetClasses` 限定范围） | `mvn org.pitest:pitest-maven:mutationCoverage` |
| 架构约束 | ArchUnit（单测形式写架构断言）、jqassistant | ArchUnit 测试随 `mvn test` 一起跑 |

## Go

| 关卡 | 工具 | 典型命令 |
|---|---|---|
| 复杂度 | gocyclo、golangci-lint（gocyclo/gocognit linter） | `gocyclo -over 10 .` |
| 测试+覆盖率 | 内置 | `go test -cover ./...` |
| 变异测试 | go-mutesting、ooze | `go-mutesting ./...` |
| 架构约束 | arch-go、go-arch-lint | 在模块根目录写好 `arch-go.yml` 后直接运行 `arch-go` |

## Rust

| 关卡 | 工具 | 典型命令 |
|---|---|---|
| 复杂度 | clippy（cognitive_complexity 等 lint） | `cargo clippy -- -D warnings` |
| 测试+覆盖率 | cargo-llvm-cov / tarpaulin | `cargo llvm-cov` |
| 变异测试 | cargo-mutants（用 `-f` glob 限定文件，或用 `--in-diff` 从 stdin 读 diff 限定范围） | `cargo mutants -f src/foo.rs`；`git diff main \| cargo mutants --in-diff -` |
| 架构约束 | 模块可见性约定（`pub(crate)`）；cargo-modules（v0.13+）：`dependencies --acyclic` 发现循环依赖即非零退出，可当门禁；`structure` 仅供查看；clippy 自定义 lint 需工程化接入，成本高，不作为最小配置 | `cargo modules dependencies --acyclic` |

## C# / .NET

| 关卡 | 工具 | 典型命令 |
|---|---|---|
| 复杂度 | Visual Studio / Roslyn 分析器（CA1502）、SonarQube | `dotnet build` + analyzers |
| 测试+覆盖率 | xUnit + coverlet | `dotnet test --collect:"XPlat Code Coverage"` |
| 变异测试 | Stryker.NET | `dotnet stryker` |
| 架构约束 | NetArchTest（单测形式；原版仓库已停更，可用社区维护的 fork NetArchTest.eNhancedEdition） | 随测试套件运行 |

## 通用建议

- **阈值起步值**：圈复杂度 10；变异击杀率以「变更代码 100% 杀死」为目标、全量基线可逐步提升；架构违规 0 容忍。
- **成本控制**：变异测试和全量复杂度扫描放在 CI nightly 或按需运行；PR 阶段只对 diff 范围做检查——Stryker 用 `--incremental`，cargo-mutants 用 `-f` 或 `--in-diff`，PIT 用 `-DtargetClasses`，mutmut/go-mutesting 按文件分批。
- **接入方式**：各道关卡统一收口到一个命令（如 `make verify` / `npm run verify`），Agent 和人共用同一个入口，避免「两套标准」。
