# Requirements: SkillScout

**Defined:** 2026-07-16  
**Status:** MVP scope approved  
**Core Value:** 从公开 GitHub 仓库中安全、可追溯地发现可复用 AI 工作流，将其转换为经过独立审核的标准 Agent Skill Draft PR，同时确保任何自动化都无法执行候选代码或绕过人工合并门禁。

## v1 Requirements

### Discovery

- [ ] **DISC-01**: 系统支持一组版本化的 GitHub Search 查询，并可通过每日定时任务或人工触发启动发现运行。
- [ ] **DISC-02**: 每次运行最多接收 100 个去重后的候选仓库，其中最多 20 个进入 LLM 分析；预算不得在运行中静默扩大。
- [ ] **DISC-03**: 每次发现输出结构化记录，包括查询版本、查询文本、分页位置、候选来源、GitHub rate-limit 信息和去重结果。

### Deterministic Filtering

- [x] **FILT-01**: 系统使用确定性规则拒绝非公开、已归档、fork、缺少默认分支或缺少 README 的明显不合格仓库。
- [x] **FILT-02**: 系统只接受明确识别为 `MIT`、`Apache-2.0`、`BSD-2-Clause` 或 `BSD-3-Clause` 的单一仓库级许可证；缺失、`NOASSERTION`、非标准、多重或冲突许可证均被拒绝。
- [x] **FILT-03**: 每条过滤规则输出规则版本、观察值、`pass/fail/not_applicable` 结果和可读理由；许可证及其他硬门槛不得交给 LLM 判断。

### Bounded Repository Reading

- [x] **READ-01**: 系统在读取前解析并固定精确 commit SHA；后续内容请求不得回退到浮动的默认分支引用。
- [x] **READ-02**: Reader 严格按照 README → `docs/` → `examples/` → 包清单 → 少量源代码的顺序读取候选内容。
- [x] **READ-03**: 默认单仓库读取预算为最多 25 个文件、其中最多 5 个源代码文件、单文件 128 KiB、累计 512 KiB、约 40,000 input tokens；政策版本可调整，但单次运行不能越过组织级上限。
- [x] **READ-04**: 证据足以支持语义判断时 Reader 提前停止，并结构化记录已读文件、blob SHA、content hash、读取顺序、预算消耗、是否读取源码和停止原因。
- [x] **READ-05**: Reader 拒绝二进制、压缩包、Git 子模块、Git LFS 内容、超预算文件、路径穿越和其他不在文本 allowlist 中的内容。
- [x] **READ-06**: 系统不得 clone 候选仓库、下载 release artifact、安装依赖、执行构建、import 候选包、运行示例或以任何方式执行候选仓库代码。

### Workflow Extraction

- [x] **EXTR-01**: Extractor 使用无工具的 LLM 请求和严格 Structured Output 判断候选是否包含可复用 AI 工作流；拒绝和 schema 失败必须是可诊断的结构化结果。
- [x] **EXTR-02**: 单个仓库最多提取 3 个相互独立的工作流，每个工作流具有独立证据和稳定 workflow fingerprint。
- [x] **EXTR-03**: 每个 `WorkflowSpec` 至少包含目标、适用条件、非目标、前置条件、输入、顺序步骤、输出、失败模式、禁止动作、必要审批、假设、证据引用和置信度。
- [x] **EXTR-04**: `WorkflowSpec` 是原始仓库内容与下游之间的唯一语义信任边界；提取完成后 Generator、Reviewer 和 Publisher 不得接收完整 README、文档或源码原文。

### Qualification

- [x] **QUAL-01**: 系统在生成 Skill 前使用版本化确定性规则评估工作流的具体性、可复用性、可验证性、证据充分性及其是否依赖未授权执行。
- [x] **QUAL-02**: 默认资格通过线为 75/100 且无硬性失败；资格结果必须输出逐项检查、得分、门槛版本、通过状态和拒绝理由。

### Skill Generation

- [x] **GEN-01**: Generator 根据通过资格门槛的 `WorkflowSpec` 生成符合 Agent Skills 规范的目录、`SKILL.md` 以及必要的 `references/` 或 `assets/`。
- [x] **GEN-02**: v1 只生成文档型 Skill，禁止创建 `scripts/`、二进制、带可执行位的文件或复制候选仓库中的可执行代码。
- [x] **GEN-03**: 生成内容必须将来源工作流改写为通用指令；必要短摘录必须受长度政策限制，并标注来源路径与 commit SHA。
- [x] **GEN-04**: 每个 Skill 包含机器可读 provenance，至少记录来源仓库 URL、GitHub repo ID、精确 commit SHA、许可证 SPDX、证据路径、blob/content hash、schema/prompt/policy 版本和生成模型。
- [x] **GEN-05**: Skill 使用符合规范的稳定 slug 和版本化 workflow fingerprint；相同来源工作流的后续有效变更应更新已有 Skill Draft，而非创建重复 Skill。

### Validation

- [x] **VAL-01**: 系统运行官方 Agent Skills 验证器，并检查 frontmatter、目录名、资源引用和 progressive-disclosure 结构。
- [x] **VAL-02**: 系统执行确定性安全和来源检查，覆盖秘密形态、危险命令、越权工具、自动下载或执行、Prompt Injection 残留、外部 URL、来源缺失、禁止的 `scripts/` 和过度复制。
- [x] **VAL-03**: Validation Report 使用结构化 `error/warning/info` 结果并记录 validator/policy 版本；任何 error 都阻止审核通过和发布。

### Independent Review

- [x] **REV-01**: Reviewer 使用与 Extractor、Generator 分离的新 LLM 请求和上下文，只接收 `WorkflowSpec`、生成的 Skill、provenance 和 Validation Report，不接收完整原始仓库内容。
- [x] **REV-02**: Reviewer 输出严格结构化的 `YES/NO`、置信度、理由、缺失假设和最小修改建议；Reviewer 只判断，不得编辑或返回替换后的 Skill 文件。
- [x] **REV-03**: 只有 Validation Report 无 error、Reviewer verdict 为 `YES` 且默认置信度不低于 0.80 的 Skill 才能进入 Publisher。

### Draft PR Publication

- [x] **PUB-01**: Publisher 只向配置的受控中央 Skill catalog 仓库创建或更新确定性机器分支、提交已验证 artifact、创建 Draft Pull Request，并请求配置的人类 reviewer 或 team。
- [x] **PUB-02**: Draft PR 正文必须包含来源仓库、commit SHA、许可证、workflow fingerprint、证据摘要、资格结果、安全/格式检查、独立审核结论及明确的人类审核提示。
- [x] **PUB-03**: Publisher 不得设置 auto-merge、调用 merge API、批准 PR、把 Draft 标记为 ready for review、修改规则集或直接向默认分支写入。
- [x] **PUB-04**: 发布身份使用最小权限短期 GitHub App installation token；catalog 默认分支 ruleset 必须在平台层阻止该身份直接写入、绕过人工审批或 merge。
- [x] **PUB-05**: Publisher 根据目标仓库、稳定 slug、发布分支和机器可读 PR marker 实现幂等；重复运行更新已有 Draft PR，并能在本地状态丢失时从远端恢复 Publication Record。

### State, Recovery, and Audit

- [x] **OPS-01**: 每个阶段均输出带 `schema_version`、稳定 ID、时间戳、input/output hash 以及 prompt/policy/model 版本的结构化数据，并通过 `StageAttempt` 记录重试、错误、请求 ID、延迟和 token 用量。
- [ ] **OPS-02**: v1 使用 SQLite 保存可查询事务状态，并用专用 `skillscout-state` 分支中的版本化 JSON manifests 提供审计与重建能力；定时和手动生产运行通过单 concurrency group 串行化。
- [ ] **OPS-03**: 持久状态、日志、Actions artifacts 和 Draft PR 不得保存完整第三方仓库正文、授权头、API 密钥或其他不必要的秘密数据。
- [x] **OPS-04**: 系统支持暂时性故障的有限重试、从最近成功阶段恢复，以及完成发布计划但不产生远程写入的 dry-run。

### Security Controls

- [x] **SEC-01**: 所有 OpenAI 请求默认 `store=false`，不提供 Web、MCP、shell、代码解释器或其他工具，不包含 GitHub/OpenAI 密钥，并将仓库内容作为低优先级不可信输入处理。
- [x] **SEC-02**: CI 使用最小 GitHub Actions 权限、固定第三方 Action commit SHA、受保护发布环境和结构化日志字段 allowlist；候选仓库数据不得直接插值到 shell 命令。

### MVP Verification

- [ ] **TEST-01**: 系统使用至少 5 个固定到 commit SHA 的真实公共仓库完成 Search 到发布决策的端到端验收。
- [ ] **TEST-02**: 验收集至少覆盖成功生成、确定性过滤、资格低分、格式/安全失败、Reviewer 拒绝和多种 Prompt Injection 输入。
- [ ] **TEST-03**: 相同 repo、commit SHA、workflow fingerprint 和政策版本重复运行时，不得重复生成 WorkflowSpec、Skill、发布分支或 Draft PR；相关来源变化必须触发重新评估并更新既有 Draft。
- [ ] **TEST-04**: MVP 必须至少创建一个需要人类审核的真实 Draft PR，并实测自动化身份无法 push 默认分支、merge、批准或读取未授权密钥。

## v2 Requirements

### Extended Sources and Scale

- **FUT-01**: 在独立授权和访问控制下支持私有 GitHub 仓库。
- **FUT-02**: 使用 embedding 或其他语义索引进行跨仓库工作流去重和相似 Skill 检索。
- **FUT-03**: 将状态 adapter 从 state branch 迁移到托管数据库和对象存储，并支持安全的并发 worker。
- **FUT-04**: 支持更多 discovery source 和可替换 LLM provider，同时保持领域阶段契约不变。

### Richer Skills and Operations

- **FUT-05**: 在专用沙箱、额外安全政策和人工授权下评估生成 `scripts/` 的能力。
- **FUT-06**: 提供人工审核队列、检索、指标和审计 Web 界面。
- **FUT-07**: 支持多租户配置、角色权限、配额与成本归属。
- **FUT-08**: 在保留再次验证和人工门禁的前提下，支持 Reviewer 意见驱动的受控修订循环。

## Out of Scope

| Capability | Reason |
|---|---|
| 自动 merge、自动批准或自动 ready-for-review | 人工审核与合并是不可绕过的核心安全边界。 |
| 执行、构建、测试或安装候选仓库代码 | 外部仓库始终是不可信供应链输入。 |
| 自动访问未授权密钥或其他组织资源 | 违反最小权限与明确授权原则。 |
| v1 生成 Agent Skill `scripts/` | 首版先验证发现、抽象和审核质量，避免引入可执行供应链。 |
| 大规模向量数据库 | MVP 规模不需要，语义去重延后。 |
| 多租户和 Web 管理后台 | 不影响核心端到端价值验证。 |
| 自动修改 SkillScout 自身代码 | 会形成未经授权的自修改闭环。 |
| 自动发布到公共 Skill 市场 | v1 只进入受控 catalog 的 Draft PR。 |
| 把固定“8 个 Agent”作为部署架构 | 阶段契约是产品边界，具体阶段可由规则、普通代码或独立 LLM 请求实现。 |
| 使用 Actions cache/artifact 作为 canonical state | 它们无法提供持久、可恢复的业务幂等保证。 |

## Requirement Dependencies

```text
DISC ─> FILT ─> READ ─> EXTR ─> QUAL ─> GEN ─> VAL ─> REV ─> PUB
  └──────────────────────── OPS + SEC ────────────────────────┘
                                  │
                                  └──────── TEST
```

- `PUB-*` 不得在 `VAL-*` 与 `REV-*` 未通过时执行。
- `EXTR-04` 是 `GEN-*`、`REV-*`、`PUB-*` 的数据边界前置条件。
- `OPS-*` 和 `SEC-*` 是所有阶段的横切要求，不得推迟到发布阶段补做。
- `TEST-04` 只有在目标 catalog ruleset 与 GitHub App 权限配置完成后才可通过。

## Traceability

Roadmap 创建后，每条 v1 requirement 必须且只能映射到一个主要交付 phase；横切验证可在后续 phase 重复，但不得失去主责任阶段。

| Requirement | Phase | Status |
|---|---|---|
| DISC-01 | Phase 5 | Pending |
| DISC-02 | Phase 5 | Pending |
| DISC-03 | Phase 5 | Pending |
| FILT-01 | Phase 2 | Complete |
| FILT-02 | Phase 2 | Complete |
| FILT-03 | Phase 2 | Complete |
| READ-01 | Phase 2 | Complete |
| READ-02 | Phase 2 | Complete |
| READ-03 | Phase 2 | Complete |
| READ-04 | Phase 2 | Complete |
| READ-05 | Phase 2 | Complete |
| READ-06 | Phase 2 | Complete |
| EXTR-01 | Phase 2 | Complete |
| EXTR-02 | Phase 2 | Complete |
| EXTR-03 | Phase 2 | Complete |
| EXTR-04 | Phase 2 | Complete |
| QUAL-01 | Phase 3 | Complete |
| QUAL-02 | Phase 3 | Complete |
| GEN-01 | Phase 3 | Complete |
| GEN-02 | Phase 3 | Complete |
| GEN-03 | Phase 3 | Complete |
| GEN-04 | Phase 3 | Complete |
| GEN-05 | Phase 3 | Complete |
| VAL-01 | Phase 3 | Complete |
| VAL-02 | Phase 3 | Complete |
| VAL-03 | Phase 3 | Complete |
| REV-01 | Phase 3 | Complete |
| REV-02 | Phase 3 | Complete |
| REV-03 | Phase 3 | Complete |
| PUB-01 | Phase 4 | Complete |
| PUB-02 | Phase 4 | Complete |
| PUB-03 | Phase 4 | Complete |
| PUB-04 | Phase 4 | Complete |
| PUB-05 | Phase 4 | Complete |
| OPS-01 | Phase 1 | Complete |
| OPS-02 | Phase 5 | Pending |
| OPS-03 | Phase 5 | Pending |
| OPS-04 | Phase 1 | Complete |
| SEC-01 | Phase 2 | Complete |
| SEC-02 | Phase 4 | Complete |
| TEST-01 | Phase 6 | Pending |
| TEST-02 | Phase 6 | Pending |
| TEST-03 | Phase 6 | Pending |
| TEST-04 | Phase 6 | Pending |

**Coverage:** 44 v1 requirements; 44 mapped; 0 unmapped.

## Approval Record

- Product scope, safety boundaries, recommended research choices, and the complete v1 requirement list were approved by the user on 2026-07-16.
- Changes to v1 scope require an explicit requirements update; implementation details may evolve only if they preserve these acceptance boundaries.

---
*Requirements defined: 2026-07-16*  
*Last updated: 2026-07-16 after vertical roadmap mapping*
