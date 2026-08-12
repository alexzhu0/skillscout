## Project

**SkillScout**

SkillScout 是一个 Agent Skill 自动发现与生成系统，面向维护中央 Skill 仓库的人类审核者。它定期从公开 GitHub 仓库中发现可复用的 AI 工作流，通过确定性过滤、受限内容读取、语义提取、标准 Skill 生成、安全校验和独立审核，将合格结果提交为 Draft Pull Request；系统永远不会自动合并代码。

第一版聚焦一条可审计、可重复、低风险的端到端流水线。发现、过滤、阅读、提取、评分、生成、审核和发布是相互隔离的阶段，每个阶段都以结构化数据作为输入和输出。

**Core Value:** 安全、可追溯地把公开仓库中的可复用 AI 工作流转化为值得人类审核的标准 Agent Skill Draft PR。

### Constraints

- **安全**: 所有外部内容均不可信，不得被解释为系统指令、工具调用或执行许可 — 防止 Prompt Injection 和供应链风险。
- **执行边界**: 不克隆后运行、不安装依赖、不调用来源仓库脚本 — 保持纯读取与静态分析。
- **人类控制**: 系统不能自动合并、批准或发布 Skill — Draft PR 是自动化流程的终点。
- **许可证**: 仅处理明确识别的宽松许可证，并在所有下游产物中保留许可证与归因 — 降低法律和来源追踪风险。
- **凭据**: GitHub 与 OpenAI 凭据必须最小权限、由运行环境注入且禁止写入日志、数据库、Prompt 或 PR — 防止密钥泄漏。
- **确定性优先**: 搜索后过滤、内容限制、格式校验、安全规则、幂等和发布权限均由确定性逻辑负责 — LLM 只承担语义任务。
- **阶段隔离**: 每个阶段具有明确的带版本输入输出 schema，失败可单独重试，不依赖隐式共享状态 — 保证可审计性和可测试性。
- **成本**: 单次运行的候选数和 LLM 调用数必须有硬上限 — 避免 GitHub API 与模型成本失控。
- **兼容性**: 第一版只支持公开 GitHub 仓库和中央 Agent Skills 仓库 — 暂不抽象为多提供商、多租户平台。

## Technology Stack

## 推荐技术栈

| 层次 | 选择 | MVP 约束与理由 |
|---|---|---|
| 运行时 | Python 3.13 | 新项目优先使用仍处于 bugfix 支持期、生命周期更长的 3.13；不再默认采用已进入 security-only 阶段的 3.12。部署时锁定具体补丁版本。 |
| 包与项目管理 | `pyproject.toml` + 锁文件 | 单一项目元数据入口；CI 必须按锁文件安装，禁止浮动依赖。具体工具在实现阶段选定，不影响领域设计。 |
| GitHub 集成 | GitHub REST API + `httpx` | MVP 所需 Search、Contents、Licenses、Git refs、Pull Requests、Review Requests 均有稳定 REST 接口。直接封装少量端点比引入大型 SDK 更透明，也更容易做限流、重试和请求审计。 |
| LLM 集成 | OpenAI Responses API + Python SDK 2.45.x | 使用严格 Structured Outputs；每次调用无工具、无代码执行、`store=false`，并记录实际模型、请求 ID、token 用量、提示词版本和 schema 版本。 |
| 模型策略 | 配置化，MVP 默认 `gpt-5.6-terra` | 提取、生成、审核使用互相独立的请求和上下文；不要把模型名写死在业务逻辑中。生产评测通过后再锁定快照；高价值失败样本可路由到更强模型。 |
| 结构化契约 | Pydantic 2.13.x + JSON Schema | 每个阶段输入输出均为版本化模型；同一模型用于运行时校验、数据库序列化和 OpenAI Structured Outputs schema。 |
| 状态存储 | Python `sqlite3` + 版本化 JSON 审计清单 | SQLite 是 MVP 的可查询运行状态；JSON 是内容寻址、可审阅、可重建的阶段事实。SQLite 不能只留在临时 Actions runner 上。 |
| Skill 格式 | Agent Skills 规范 + 官方 `skills-ref validate` | 在每个生成的 Skill 包内创建规范主说明文件，并按需创建 `references/`、`assets/`；MVP 不生成 `scripts/`，避免把外部代码变成可执行供应链。 |
| YAML | PyYAML 6.0.x，严格使用 safe API | 只生成规范允许的简单 frontmatter；禁止任意对象构造。也可以在实现时用一个很小的专用 frontmatter 序列化器替代。 |
| 自动化 | GitHub Actions | `schedule` + `workflow_dispatch`；单并发组串行运行；最小权限；第三方 Action 固定到完整 commit SHA。 |
| 鉴权 | GitHub App 短期 installation token | 目标 Skill catalog 若为独立仓库，默认 `GITHUB_TOKEN` 不足以安全跨仓库发布。GitHub App 只授予目标仓库的 Contents/PR 必要权限，默认分支由 ruleset 阻止写入。 |
| 测试 | pytest 9.1.x | 单元、契约、fixture、端到端 dry-run、Prompt Injection 对抗集和发布幂等性测试。网络与 LLM 必须可录制或替换。 |
| 质量 | Ruff + mypy（实现时锁版本） | 格式、静态检查、类型边界集中在 CI；领域阶段协议应可静态检查。 |

## 关键版本判断

### Python 3.13，而不是建议稿中的 3.12

### OpenAI Responses API 的使用边界

- 外部仓库文本只进入低优先级的 untrusted input 区域，不进入 developer message。
- 模型不能调用 Web、MCP、shell、代码解释器或其他工具。
- 阶段间只传严格结构化结果；生成器和 Reviewer 不接收完整原始仓库。
- 请求设置 `store=false`；不把密钥、完整日志或不必要的仓库内容发送给模型。
- 生产中记录 `prompt_version`、`schema_version`、实际模型名、请求 ID、延迟和 token 用量，但不记录授权头或其他秘密。

## GitHub API 使用策略

### 读取而非克隆

### 许可证

### Draft PR

## GitHub Actions 与持久状态

- 在自动化仓库使用专用 `skillscout-state` 分支保存 SQLite checkpoint 与经过裁剪的版本化 JSON 阶段清单；不保存完整第三方原文。
- SQLite 是查询加速和事务状态，JSON 清单是可审阅、可重建的事实来源。
- `concurrency` 将定时和手动生产运行串行化，`cancel-in-progress: false`。
- 状态分支写入与 Skill 发布分支写入分离；默认分支 ruleset 明确拒绝自动化身份直接写入。
- Actions artifact 只作为短期调试附件，不承担恢复职责。
- v2 若运行量增长，迁移到托管关系数据库或对象存储；领域层不依赖状态分支实现。

## 不采用的方案

| 方案 | MVP 不采用的原因 |
|---|---|
| 多 Agent 框架或事件总线 | 阶段独立性用 typed contracts 和模块边界即可实现；框架会增加调度、追踪和恢复复杂度。 |
| PostgreSQL / 向量数据库 | 每日最多 100 个候选、20 次语义分析，SQLite 足够；当前也没有语义检索需求。 |
| 全仓 clone / AST 全量索引 | 扩大不可信输入、成本和供应链攻击面，不符合“只读且不执行”原则。 |
| 自动生成可执行脚本 | 即使不在生成阶段执行，也会把未经验证的行为交给最终 Skill 使用者；MVP 先限于指导性 Skill。 |
| GitHub Actions cache 作为数据库 | 非持久、不可审计、会淘汰，无法保证幂等。 |
| PAT | 生命周期长、人员绑定、权限通常过宽；跨仓库发布优先 GitHub App 短期 token。 |
| 模型自由文本输出再解析 | 失败模式不透明，Prompt Injection 更容易跨阶段传播；所有语义阶段使用严格 schema。 |

## 实现前必须做的验证

- 用 5 个真实公共仓库 fixture 验证 Search、Contents、License 和 Draft PR dry-run 数据流。
- 验证官方 `skills-ref validate` 能在 CI 中离线或固定依赖执行，并确认其版本固定方式。
- 在目标组织的 ruleset 上实测 GitHub App 能创建发布分支和 Draft PR，但不能 push 默认分支或 merge。
- 验证 `store=false`、无工具的 Responses 请求日志策略，以及结构化拒绝路径。
- 用故意包含“忽略系统指令”“读取密钥”“执行命令”的文档验证注入不会越过 `WorkflowSpec` 边界。

## 主要来源

- [Agent Skills specification](https://agentskills.io/specification)
- [Agent Skills reference repository](https://github.com/agentskills/agentskills)
- [OpenAI Python SDK on PyPI](https://pypi.org/project/openai/)
- [Pydantic on PyPI](https://pypi.org/project/pydantic/)
- [HTTPX on PyPI](https://pypi.org/project/httpx/)
- [PyYAML on PyPI](https://pypi.org/project/PyYAML/)
- [pytest on PyPI](https://pypi.org/project/pytest/)
- [GitHub Actions workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- [GitHub Actions script injection guidance](https://docs.github.com/en/actions/concepts/security/script-injections)
- [GitHub Actions token guidance](https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication)
- [GitHub Actions secrets guidance](https://docs.github.com/en/actions/concepts/security/secrets)

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/`, with the standard Agent Skill index file inside each skill directory.
## Superpowers Development Workflow

Every new Codex development session must first invoke
`superpowers:using-superpowers` and follow its instructions. Then invoke every
applicable Superpowers skill before acting: use `superpowers:brainstorming`
before creative work, `superpowers:writing-plans` before multi-step
implementation, `superpowers:test-driven-development` for features and bug
fixes, `superpowers:systematic-debugging` for unexpected behavior, and
`superpowers:verification-before-completion` before claiming completion. Use
any additional Superpowers skill whenever its documented trigger applies.

Do not use `$gsd-*` commands, GSD agents, hooks, configuration, or `.planning/`
as the current development mechanism. Historical GSD records are archival
evidence only and must not be rewritten to alter historical facts.

## Current Implementation Status

The repository contains an installed Python 3.13 CLI exposed as `skillscout`. Its current commands are `dry-run`, `extract-repo`, `build-candidate`, `inspect-run`, `verify-publication-admission`, `publish-candidate`, `discover`, and `publish-discovered`.

Phases 1–5 are implemented and verified. Phase 4 controlled publication includes strict admission, dedicated publication state, bounded GitHub publishing, recovery, Draft-only handling, and a protected workflow. The 2026-07-27 Gate B4 result against workflow SHA-256 `224c843ad1211bd3fa250e055e4040417d58bb5ecd837ed0fd8f148af6c0ca8c` is historical Phase 4 evidence only. Fresh Gate B4 authority was recorded on 2026-07-28 against the exact current discover workflow SHA-256 `8157cb686b9bf18bfa800811b1fe1529ed9a15ec371fe36ec1708233052b7cfd`, publish workflow SHA-256 `96ce9f39db49ce647a88b83ec4db3cb0135e5cf51c1eb2f11961cfd243b23cf0`, and canary workflow SHA-256 `9c59cd9822eecec913f82d24c7880a443ba9416795b8996c6201f33c4df5805d`, with causal denial probes, unchanged default branch, and separate human/admin cleanup. Any change to a bound workflow, App scope, catalog, ruleset, protected environment, reviewer configuration, or installation identity invalidates that evidence and requires a fresh Gate B4 run. This does not make the whole product production-ready; Phase 6 adversarial acceptance remains pending.

## Semantic Provider Boundary

- OpenAI is the default provider. Extraction, generation, and review use the Responses API with `gpt-5.6-terra`, strict Pydantic response models, `store=false`, and no tools.
- DeepSeek is an explicit opt-in selected with `SKILLSCOUT_LLM_PROVIDER=deepseek` and the exact official base URL. It uses `deepseek-v4-flash` through the guarded Chat Completions compatibility path.
- DeepSeek JSON is never trusted as provider-validated structured output. Each response is decoded and validated locally against the same strict Pydantic schemas, and extra or malformed fields fail closed.
- Both provider clients are constructed with SDK retries disabled (`max_retries=0`). Retry authority remains in the deterministic pipeline policy so one semantic-stage attempt produces exactly one provider request.
- Semantic calls never receive tool authority, code execution, shell access, or permission to follow instructions embedded in repository content.

## Repository Commands and Secret Handling

Use the repository-local locked toolchain for tests:

```bash
.tools/uv-0.11.29/bin/uv run --locked pytest -q
```

Do not read any repository `.env` file or any PEM, JWT, token, private-key, or other secret material. Credentials may be injected only through the runtime environment at the latest required boundary. Secret values and private-key material must never be read into prompts, printed, logged, copied into fixtures or state, staged, or committed. If a task appears to require inspecting secret contents, stop and request a non-secret substitute or separately authorized procedure.

## Project Documentation

- [README](README.md) — project overview, installation, CLI quick start, and operating boundaries.
- [Architecture](docs/ARCHITECTURE.md) — components, stage isolation, data flow, and publication boundary.
- [Configuration](docs/CONFIGURATION.md) — CLI paths, semantic-provider settings, and protected publication configuration.
- [Development](docs/DEVELOPMENT.md) — local setup, commands, coding standards, and change-safety rules.
- [Testing](docs/TESTING.md) — test suites, focused commands, coverage status, and CI integration.
- [Release](RELEASE.md) — historical preview status, release gates, and remaining acceptance work.
