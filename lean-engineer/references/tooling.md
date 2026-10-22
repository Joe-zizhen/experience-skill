# 各语言质量门工具速查

按关卡分组。优先使用项目已有配置；以下为各生态主流选择，安装前先在 manifest / lockfile 中确认是否已存在。**本表是预审快捷清单，不是白名单**：缺条目或缺整个生态不构成不装理由，检索、核实、直建与回写口径见 SKILL.md「质量门工具直建」——清单靠使用增长。质量门工具直建按 SKILL.md「质量门工具直建」预授权执行；其余安装仍按「缺口必问」征得用户同意。条目以官方文档 / 官方仓库 / 包注册表核实为准，标注「已停更勿用」的不得再推荐。

## JavaScript / TypeScript

| 关卡 | 工具 | 典型命令 / 配置 |
|---|---|---|
| 复杂度 | ESLint `complexity` 规则（需项目已有 eslint 配置；ESLint 9 起无配置文件会直接报错，先 `npm init @eslint/config` 创建） | `eslint --rule '{"complexity":["error",10]}' src/` |
| 测试+覆盖率 | vitest / jest（自带 coverage） | `vitest run --coverage` |
| 变异测试 | Stryker（支持原生增量模式） | `npx stryker run`（增量：`--incremental`） |
| 架构约束 | dependency-cruiser（含 `no-circular` 循环依赖门）；eslint-plugin-boundaries；madge 已停更勿用 | `depcruise src --validate .dependency-cruiser.js` |

## Python

| 关卡 | 工具 | 典型命令 |
|---|---|---|
| 复杂度 | ruff C901（mccabe，门禁一线，`lint.mccabe.max-complexity`）；lizard（备选）；radon、xenon 已停更勿用 | `ruff check --select C901`；`lizard src/ -C 10` |
| 测试+覆盖率 | pytest + coverage.py | `pytest --cov=src --cov-fail-under=80` |
| 变异测试 | mutmut（Windows 需 WSL）、cosmic-ray（无原生增量开关，按文件/模块分批运行控制成本） | `mutmut run && mutmut results` |
| 架构约束 | import-linter（分层契约，门禁用它）；pydeps 只是依赖图可视化工具，循环依赖只在图里高亮，不能充当门禁 | `lint-imports` |

## Java / Kotlin

| 关卡 | 工具 | 典型命令 |
|---|---|---|
| 复杂度 | detekt（Kotlin 首选，Gradle 插件；阈值规则 `complexity.CyclomaticComplexMethod`，键 1.x `threshold` / 2.x `allowedComplexity`）；PMD、Checkstyle（Java 侧，不解析 Kotlin）；SonarQube（服务型基础设施，不属直建）/ SonarLint（IDE 插件，不作 CI 门） | `./gradlew detekt`（随 check）；Maven 无官方一等插件（antrun 调 CLI 或社区包装） |
| 测试+覆盖率 | JUnit + JaCoCo | `./gradlew test jacocoTestReport`（report 不依赖 test）；`mvn verify`（绑 prepare-agent + report） |
| 变异测试 | PIT (PITest)（无增量开关，`targetClasses` 限定范围；Gradle 插件不直支 Android，Android 需 fork） | `./gradlew pitest`（`info.solidsoft.pitest`，`pitest { targetClasses }`）；`mvn test-compile org.pitest:pitest-maven:mutationCoverage` |
| 架构约束 | ArchUnit（JVM 字节码级）；konsist（Kotlin 语义级）；jqassistant | 规则写成 JUnit 测试随 `./gradlew test` / `mvn test` 跑 |

## Go

| 关卡 | 工具 | 典型命令 |
|---|---|---|
| 复杂度 | gocyclo、golangci-lint（gocyclo/gocognit linter） | `gocyclo -over 10 .` |
| 测试+覆盖率 | 内置 | `go test -cover ./...` |
| 变异测试 | 无一线推荐（go-mutesting 已停更）；候选 gremlins、ooze（均 0.x，接入形态各异） | 按候选官方文档 |
| 架构约束 | arch-go、go-arch-lint | 在模块根目录写好 `arch-go.yml` 后直接运行 `arch-go` |

## Rust

| 关卡 | 工具 | 典型命令 |
|---|---|---|
| 复杂度 | clippy `cognitive_complexity`（restriction 级默认 allow，须显式开） | `cargo clippy -- -D clippy::cognitive_complexity`（门槛 `clippy.toml` `cognitive-complexity-threshold`） |
| 测试+覆盖率 | cargo-llvm-cov / tarpaulin | `cargo llvm-cov` |
| 变异测试 | cargo-mutants（用 `-f` glob 限定文件，或用 `--in-diff` 从 stdin 读 diff 限定范围） | `cargo mutants -f src/foo.rs`；`git diff main \| cargo mutants --in-diff -` |
| 架构约束 | 模块可见性约定（`pub(crate)`）；cargo-modules（v0.13+）：`dependencies --acyclic` 发现循环依赖即非零退出，可当门禁；`structure` 仅供查看；clippy 自定义 lint 需工程化接入，成本高，不作为最小配置 | `cargo modules dependencies --acyclic` |

## C# / .NET

| 关卡 | 工具 | 典型命令 |
|---|---|---|
| 复杂度 | Roslyn CA1502（.NET 10 默认不启用，须 `.editorconfig` 显式开；门槛 `CodeMetricsConfig.txt`）、SonarQube | `dotnet build` + analyzers |
| 测试+覆盖率 | xUnit + coverlet | `dotnet test --collect:"XPlat Code Coverage"` |
| 变异测试 | Stryker.NET | `dotnet stryker` |
| 架构约束 | ArchUnitNET（`TngTech.ArchUnitNET`，规则写成单测断言；NetArchTest 及其 fork 已停更勿用） | 随测试套件运行 |

## C / C++

| 关卡 | 工具 | 典型命令 |
|---|---|---|
| 复杂度 | lizard（圈复杂度 CCN；不展开宏，宏密集代码会失真）；clang-tidy `readability-function-cognitive-complexity`（认知复杂度，与 CCN 不同指标，阈值不可混用） | `lizard src/ -C 10`（超限非零退出）；clang-tidy 在 `.clang-tidy` 设 `readability-function-cognitive-complexity.Threshold`（默认 25） |
| 测试+覆盖率 | GoogleTest + CTest + gcov/lcov（GCC）或 llvm-cov（Clang） | `ctest --output-on-failure`；`lcov --directory build --capture -o app.info` / `llvm-cov report` |
| 变异测试 | Mull（现行 CLI `mull-runner`；按测试二进制退出码判杀灭，`--mutation-score-threshold` 门槛；预编译包无 Windows，须与 Clang/LLVM 主版本严格对齐） | `mull-runner-<N> --mutation-score-threshold 80 <测试二进制>` |
| 架构约束 | 无一线推荐（无跨构建系统门禁标准）：构建目标边界靠构建系统（Bazel `layering_check`）、循环 include 用 clang-tidy `misc-header-include-cycle`；include-what-you-use 只管 include 精简，不当架构门禁 | `bazel build --features=layering_check //...` |

## Swift / iOS

| 关卡 | 工具 | 典型命令 |
|---|---|---|
| 复杂度 | SwiftLint `cyclomatic_complexity`（默认 warning 10 / error 20） | `swiftlint lint --strict`（配置 `.swiftlint.yml`） |
| 测试+覆盖率 | XCTest + xcodebuild/xccov（Xcode 工程）或 SwiftPM | `xcodebuild test ... -enableCodeCoverage YES -resultBundlePath t.xcresult` → `xcrun xccov view --report t.xcresult`；SPM：`swift test --enable-coverage`（旧工具链 `--enable-code-coverage`） |
| 变异测试 | Muter（Swift 唯一一线；仅 macOS、仅 Swift） | `muter init` 后 `muter` |
| 架构约束 | 无一线推荐（Harmonize / swift-bylaws 双活无共识；SwiftLint `custom_rules` 仅正则级） | — |

## Dart / Flutter

| 关卡 | 工具 | 典型命令 |
|---|---|---|
| 复杂度 | `dart analyze` + `package:flutter_lints`（官方 lint 门禁；纯复杂度指标免费侧无一线，DCM 已商业化勿当免费一线） | `flutter analyze` |
| 测试+覆盖率 | `flutter test --coverage`（纯 Dart 用 `package:coverage`） | `flutter test --coverage`（产出 `coverage/lcov.info`） |
| 变异测试 | 无一线推荐（mutation_test / butcher 并存无共识） | 候选 `dart run mutation_test` |
| 架构约束 | `import_lint`（import / 分层规则；2.x 要 Dart 3.10+ / Flutter 3.38+，老项目用 1.x） | `dart run import_lint` |

## PHP

| 关卡 | 工具 | 典型命令 |
|---|---|---|
| 复杂度 | PHPMD（codesize 规则集 CyclomaticComplexity；3.x CLI 已改版，文档站仍展示 2.x 格式） | `phpmd analyze`（3.x，配置 phpmd.yml）；2.x 为 `phpmd src text codesize` |
| 测试+覆盖率 | PHPUnit + pcov / Xdebug（分支/路径覆盖须 Xdebug） | `vendor/bin/phpunit --coverage-clover build/coverage/clover.xml` |
| 变异测试 | Infection（MSI 门槛须显式设，否则不构成门禁） | `vendor/bin/infection --min-msi=80` |
| 架构约束 | deptrac（分层门禁，违规非零退出；装 `deptrac/deptrac`，`qossmic/deptrac` 已废弃） | `vendor/bin/deptrac analyse`（`analyze` 为等价别名） |

## Ruby

| 关卡 | 工具 | 典型命令 |
|---|---|---|
| 复杂度 | RuboCop Metrics（CyclomaticComplexity Max=7 / PerceivedComplexity Max=8；下一 major 拟默认关闭，门禁须显式启用） | `bundle exec rubocop --only Metrics/CyclomaticComplexity,Metrics/PerceivedComplexity` |
| 测试+覆盖率 | RSpec + SimpleCov（门槛写在 SimpleCov 配置；`SimpleCov.start` 放在一切 require 之前） | `bundle exec rspec` |
| 变异测试 | mutant（开源免费须 `--usage opensource`；**商用须付费订阅**；仅 Linux/macOS，无 Windows） | `mutant run --use rspec --usage opensource 'Subject#method'` |
| 架构约束 | packwerk（包边界/常量可见性；只做静态常量引用分析，方法调用不检查） | `bin/packwerk check` |

## 通用建议

- **阈值起步值**：圈复杂度 10；变异击杀率以「变更代码 100% 杀死」为目标、全量基线可逐步提升；架构违规 0 容忍。
- **成本控制**：变异测试和全量复杂度扫描放在 CI nightly 或按需运行；PR 阶段只对 diff 范围做检查——Stryker 用 `--incremental`，cargo-mutants 用 `-f` 或 `--in-diff`，PIT 用 `targetClasses` 限定范围，mutmut 按文件分批。
- **接入方式**：各道关卡统一收口到一个命令（如 `make verify` / `npm run verify`），Agent 和人共用同一个入口，避免「两套标准」。
- **横切脚本层**：SQL、Bash / Shell（含 PowerShell）等横切层无完整三关生态——风格 / 静态检查类工具不等于三关门禁，变异与架构关无一线推荐，走检索回写。
