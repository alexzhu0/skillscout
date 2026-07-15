# 系统架构研究

**项目：** SkillScout  
**研究日期：** 2026-07-15  
**推荐形态：** 单仓库、模块化 CLI/worker、显式阶段契约、串行可恢复流水线

## 架构结论

MVP 应采用模块化单体，而不是微服务或多 Agent 平台。每个阶段都是一个只接受版本化结构对象、只返回版本化结构对象的 processor；编排器负责预算、重试、幂等和状态推进。只有 Extractor、Generator、Reviewer 调用 LLM，而且三者使用独立请求。

这种结构保留了“发现、过滤、阅读、提取、评分、生成、审核、发布彼此独立”的核心要求，同时让本地 CLI、pytest 和 GitHub Actions 复用同一条业务流水线。

## 系统上下文

```text
                         ┌───────────────────────────┐
 schedule / manual ────> │ SkillScout GitHub Action  │
                         └─────────────┬─────────────┘
                                       │ invokes CLI
                              ┌────────▼────────┐
                              │ Pipeline Runner │
                              └───┬─────────┬───┘
                                  │         │
                 read-only REST   │         │ structured, no tools
                         ┌────────▼───┐   ┌─▼──────────────┐
                         │ GitHub API │   │ OpenAI Responses│
                         └────────────┘   └────────────────┘
                                  │
                       structured audit/state
                         ┌────────▼──────────────┐
                         │ state branch          │
                         │ SQLite + JSON manifests│
                         └───────────────────────┘
                                  │ approved output only
                         ┌────────▼──────────────┐
                         │ controlled Skill repo │
                         │ branch + Draft PR     │
                         └────────┬──────────────┘
                                  │ human review/merge only
                              ┌───▼───┐
                              │ Human │
                              └───────┘
```

## 阶段与信任边界

| 阶段 | 输入 | 输出 | 类型 | 允许的外部能力 |
|---|---|---|---|---|
| Scout | `RunConfig`, prior cursors | `CandidateRepository[]` | 确定性 | GitHub Search，只读 |
| Filter | candidates, policy | `FilterDecision[]` | 确定性 | GitHub metadata/license，只读 |
| Reader | accepted revision, budget | `ReadSnapshot` | 确定性 | GitHub contents/tree，只读 |
| Extractor | bounded untrusted snapshot | `WorkflowExtraction` | LLM | Responses API；无 tools |
| Qualifier | `WorkflowSpec`, provenance | `QualificationDecision` | 确定性 | 无 |
| Generator | qualified `WorkflowSpec` | `SkillArtifact` | LLM | Responses API；无 tools |
| Validators | artifact, policy, provenance | `ValidationReport` | 确定性 | 本地 validator；不执行生成内容 |
| Reviewer | spec, artifact, reports | `ReviewDecision` | 独立 LLM | Responses API；无 tools |
| Publisher | approved release bundle | `PublicationRecord` | 确定性 | 目标 catalog Git/PR API，有限写 |

### 最重要的边界

`ReadSnapshot` 是不可信内容容器，只有 Extractor 可以消费。Extractor 输出经过 schema 验证的 `WorkflowSpec` 后，Generator、Reviewer 与 Publisher 不再接收 README、源码或任意仓库原文。证据只以路径、blob SHA、content hash 和必要的短摘录表示。

这实现了 OpenAI 安全指南中“不要让不可信文本直接驱动后续行为”和“用结构化节点限制跨阶段数据通道”的原则。参考 [OpenAI Agent safety](https://developers.openai.com/api/docs/guides/agent-builder-safety)。

## 组件边界

```text
skillscout/
  domain/        # Pydantic contracts, enums, IDs, policies
  stages/        # one module per pipeline stage; no provider details
  orchestration/ # state machine, budgets, retries, idempotence
  adapters/
    github/      # search/read/license/publish clients
    openai/      # structured Extractor/Generator/Reviewer clients
    state/       # SQLite + JSON manifest repository
    skills/      # Agent Skills renderer and validators
  policies/      # versioned deterministic filters/scores/security rules
  cli/           # discover, run, resume, dry-run, inspect
tests/
  fixtures/      # frozen GitHub responses and adversarial documents
  contracts/
  integration/
  e2e/
```

这是未来实现建议，不代表当前阶段要创建代码。领域模块不得 import GitHub/OpenAI SDK；stages 只依赖 ports/protocols，便于测试替身和未来更换 provider。

## 数据模型

所有顶层记录统一包含：`schema_version`、稳定 ID、`created_at`、`input_hash`、`output_hash`；所有模型/规则产生的记录还包含对应 `prompt_version` 或 `policy_version`。

### 核心实体

| 实体 | 关键字段 | 约束与用途 |
|---|---|---|
| `Run` | `run_id`, trigger, status, config_hash, started/finished, candidate/LLM budgets, usage | 一次 scheduled/manual/dry-run 的根；预算不可在中途静默扩大。 |
| `SearchQuery` | query_id, query_text, sort/order, cursor, policy_version | 查询本身版本化，可解释候选为何出现。 |
| `CandidateRepository` | GitHub repo ID, full_name, URL, visibility, fork/archived, stars, topics, default_branch | GitHub numeric repo ID 是主身份，避免 rename 造成重复。 |
| `RepositoryRevision` | repo_id, commit_sha, ref, license_spdx, discovered_at | 唯一约束 `(repo_id, commit_sha)`；所有读取固定到 SHA，禁止漂移。 |
| `FilterDecision` | revision_id, checks[], passed, reasons, policy_version | 每个确定性检查保留观察值。 |
| `SourceDocument` | revision_id, path, kind, blob_sha, size, content_hash, loaded_order | 默认不持久化完整正文；标识一份已读证据。 |
| `ReadSnapshot` | snapshot_id, revision_id, document refs, bytes/tokens, source_code_loaded, stop_reason | Reader 的有界输出和成本证据。 |
| `WorkflowSpec` | workflow_id, fingerprint, goal, applicability, inputs, ordered steps, outputs, failure_modes, assumptions, evidence[], confidence | 语义信任边界；唯一约束 `(revision_id, fingerprint)`。 |
| `QualificationDecision` | workflow_id, checks[], score, threshold, passed, policy_version | 生成前的确定性质量门。 |
| `SkillArtifact` | skill_id, slug, workflow_id, files[], artifact_hash, provenance | `slug` 满足 Agent Skills name 规则；files 保存路径与 hash。 |
| `ValidationReport` | skill_id, checks[], highest_severity, passed, validator_versions | 格式、安全、归属和相似度检查统一报告。 |
| `ReviewDecision` | skill_id, reviewer_model, prompt_version, verdict, confidence, reason, missing_assumptions, minimum_changes | Reviewer 只判断，不包含修改后的文件。 |
| `PublicationRecord` | skill_id, target_repo, branch, commit, PR number/URL, state, marker | 唯一活动发布 `(target_repo, slug)`；只允许 Draft。 |
| `StageAttempt` | run_id, subject_id, stage, attempt_no, status, started/finished, request_id, token_usage, error_code, artifact_ref | 支持恢复、重试和运维审计。 |

### `WorkflowSpec` 建议结构

```text
WorkflowSpec
├── identity: workflow_id, fingerprint, schema_version
├── intent: title, goal, applicability, non_goals
├── interface: inputs[], outputs[], prerequisites[]
├── procedure: ordered steps[]
│   └── id, instruction, inputs, outputs, failure_conditions
├── safety: prohibited_actions[], required_approvals[]
├── failure_modes[]: condition, signal, response
├── assumptions[]
├── evidence[]: path, blob_sha, content_hash, short_excerpt, supports
└── confidence: overall, uncertainties[]
```

Fingerprint 应基于规范化后的工作流语义和来源仓库身份，而不是模型生成标题；精确算法必须版本化，例如 `sha256(repo_id + normalized goal/steps + fingerprint_version)`。

## 状态机

```text
DISCOVERED
  ├─filter fail────────────> FILTERED_OUT
  └─filter pass────────────> READY_TO_READ
                               ├─read fail────> READ_FAILED
                               └──────────────> READ_COMPLETE
                                                  ├─no workflow──> NO_WORKFLOW
                                                  └──────────────> EXTRACTED
                                                                     ├─gate fail──> NOT_QUALIFIED
                                                                     └────────────> GENERATED
                                                                                       ├─validate fail─> INVALID
                                                                                       └───────────────> REVIEWED
                                                                                                          ├─NO──> REJECTED
                                                                                                          └─YES─> PUBLISHABLE
                                                                                                                   └─> DRAFT_PR
```

错误状态与业务拒绝状态分离：许可证不符合是稳定的 `FILTERED_OUT`，429/网络失败是可重试 `StageAttempt` 错误。只有暂时性错误自动重试；schema 不匹配最多有限次数，再转人工诊断。

## 幂等与更新策略

### 处理键

- Revision：`repo_id + commit_sha`。
- Read result：`revision_id + reader_policy_version + budget_hash`。
- Workflow：`revision_id + workflow_fingerprint_version + fingerprint`。
- Generation：`workflow_id + generator_prompt_version + skill_spec_version`。
- Review：`artifact_hash + validation_hash + reviewer_prompt_version + model`。
- Publication：`target_repo + skill_slug`，PR body 另含不可见机器 marker。

### 来源更新

1. 默认分支 SHA 未改变：复用已有阶段结果。
2. SHA 改变但已读文件 hash 均未改变：保留旧工作流结果，记录 revision alias。
3. 相关证据改变：重新提取、打 fingerprint、生成和审核。
4. fingerprint 命中已有 slug：更新同一发布分支和 Draft PR。
5. fingerprint 消失或语义发生破坏性变化：不自动删除已发布 Skill；在 Draft PR 中提示人工决定。

Publisher 在本地状态丢失时，仍要按远程 branch、head ref 和 PR marker 查找已有 Draft，从而避免重复发布。

## 持久化设计

### MVP 方案

- `skillscout-state` 分支只存自动化状态，不参与默认分支代码发布。
- `state/skillscout.db`：事务状态、索引、查询视图。
- `state/manifests/<run>/<stage>/<subject>.json`：经过裁剪的结构化阶段输出；按 hash 校验，可重建 SQLite。
- 不持久化完整 README/源码正文；短证据摘录遵守引用与许可证政策。
- 单个生产 concurrency group 串行修改状态分支。
- 成功完成候选或发布副作用后写 checkpoint；写入使用远端 head 条件检查。

SQLite 作为二进制文件会造成 Git 历史增长，因此这是有预算和保留策略的 MVP 折中。达到以下任一条件就迁移：数据库 >100 MB、日处理量持续超过 MVP 10 倍、需要多人并发写、状态 push 成为主要故障源。

### 不把 cache/artifact 当状态

GitHub-hosted runner 是临时的；cache 可淘汰且不可变，artifact 有保留期并会随 run 删除。它们可以用于依赖或调试，但不能提供“相同 SHA 不重复 PR”的业务保证。参考 [GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)、[Dependency caching](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching) 与 [Workflow artifacts](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts)。

## GitHub Actions 拓扑

```text
discover.yml
  triggers: daily cron + workflow_dispatch
  permissions: contents: read for source automation repo
  concurrency: skillscout-production / no cancellation
  jobs:
    prepare-state     # checkout code + dedicated state branch
    pipeline          # run bounded CLI, no untrusted code execution
    publish           # only if approved, GitHub App token, target catalog
    checkpoint        # persist structured state and audit metadata
```

实际 workflow 可拆成 jobs，但不要通过 shell 插值直接使用不可信 GitHub context。workflow permissions 从无权限开始显式增加；发布 job 使用受保护 environment 和短期 GitHub App token。GitHub 官方说明 schedule/workflow_dispatch 在默认分支上生效，并建议最小化 `GITHUB_TOKEN` 权限。参考 [Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)、[Script injections](https://docs.github.com/en/actions/concepts/security/script-injections)、[Automatic token authentication](https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication) 与 [Secrets](https://docs.github.com/en/actions/concepts/security/secrets)。

## 发布安全

自动化安全不能只靠“提示词说不要 merge”。必须由权限系统形成硬约束：

- Catalog 默认分支 ruleset 要求 PR、人类审批和必需检查。
- GitHub App 不在 bypass list，不能 direct push 默认分支。
- App 只安装在自动化仓库与目标 catalog，权限只含 metadata read、contents write、pull requests write；不授予 administration、actions write、secrets 或 members。
- Publisher 客户端不实现 merge 方法；HTTP allowlist 拒绝 merge/auto-merge/branch-protection 管理端点。
- 发布分支名前缀固定且 slug 转义；提交内容只能来自已验证 artifact manifest。
- PR 始终 `draft=true`，并请求配置的人类 reviewer/team。
- 凭据永不进入模型输入、SQLite、artifact、PR body 或日志；GitHub 的自动 redaction 不是充分保护。

## 失败、重试与恢复

| 故障 | 行为 |
|---|---|
| GitHub 429 / secondary rate limit | 尊重 headers 与 `Retry-After`，带抖动退避；不消耗新的候选预算。 |
| GitHub 404/409 at fixed SHA | 重取 revision metadata；仍不一致则记录稳定失败，不回退到浮动 default branch。 |
| OpenAI timeout/5xx | 有限重试同一 input hash；保存 request ID。 |
| Structured Output refusal | 保存结构化 refusal，停止该工作流，不降级为自由文本。 |
| Schema validation failure | 有限的 schema repair 重试；仍失败进入诊断队列。 |
| Validator error | 阻止 Review/Publish；不让 Reviewer 覆盖确定性错误。 |
| Reviewer `NO` | 记录结果，终止；MVP 不自动改写并再次审核。 |
| PR 已存在 | 根据 head/marker 更新同一 Draft；若不是 Draft 或由人类改动冲突，停止并请求人工。 |
| PR 创建成功但状态写入失败 | 下一 run 先查远端 marker 恢复 publication record。 |
| 状态分支 push 冲突 | 因单 concurrency 理论上少见；重新读取远端 head，验证无不同生产 run 后再重试。 |

## 测试架构

- Contract tests：每个 Pydantic schema 的兼容性、hash 稳定性、迁移与拒绝路径。
- Policy tests：许可证、路径、预算、评分和安全规则的表驱动测试。
- Adapter tests：录制/fixture GitHub REST 与 OpenAI Structured Outputs，不依赖实时服务。
- Adversarial tests：README/doc 中包含工具调用诱导、密钥窃取、base64 隐藏指令、引用污染和超长输入。
- Publication tests：远端 fake 验证只使用允许端点；重复执行更新 Draft，不创建重复 PR。
- E2E dry-run：5 个固定公共仓库 SHA，产出完整审计链但不写远端。
- Live canary：受控 catalog 测试仓库，验证 branch protection 和 Draft PR，需人工触发。

## 可演进边界

模块化单体不是永久限制。未来可以在不改领域契约的情况下：

- 把 state adapter 从 SQLite/state branch 替换为 Postgres + object storage。
- 把日常 runner 替换为队列 worker。
- 增加其他 discovery source 或模型 provider。
- 为经过更严格沙箱与人工政策批准的 Skill 生成 `scripts/`。

在 MVP 数据证明吞吐或可靠性需要之前，不提前引入这些复杂度。

