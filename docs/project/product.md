# SkillScout

## What This Is

SkillScout 是一个 Agent Skill 自动发现与生成系统，面向维护中央 Skill 仓库的人类审核者。它定期从公开 GitHub 仓库中发现可复用的 AI 工作流，通过确定性过滤、受限内容读取、语义提取、标准 Skill 生成、安全校验和独立审核，将合格结果提交为 Draft Pull Request；系统永远不会自动合并代码。

第一版聚焦一条可审计、可重复、低风险的端到端流水线。发现、过滤、阅读、提取、评分、生成、审核和发布是相互隔离的阶段，每个阶段都以结构化数据作为输入和输出。

## Core Value

安全、可追溯地把公开仓库中的可复用 AI 工作流转化为值得人类审核的标准 Agent Skill Draft PR。

## Requirements

### Validated

- ✓ 每个流水线阶段都输出带版本的结构化记录，便于审计、重试和故障定位。 — Phase 1（九阶段流水线：StageEnvelope/StageAttempt/不可变 resume 事件，5/5 must-haves 通过）
- ✓ 系统使用确定性规则过滤元数据、仓库状态和许可证；不明确或不在允许列表的许可证必须在 LLM 前失败。 — Phase 2
- ✓ Reader 仅通过 GitHub REST 读取固定 commit 下的允许文本，按 README → docs → examples → manifests → source 排序，受五类硬预算与显式停止原因约束。 — Phase 2
- ✓ 所有外部内容均为不可信数据：不 clone、安装、构建、import 或执行候选代码；Prompt Injection 样本无法获得指令或工具权限。 — Phase 2
- ✓ LLM 仅在确定性门禁通过后执行一次无工具、`store=false` 的严格结构化语义提取，可输出 0–3 个独立工作流。 — Phase 2
- ✓ 提取后仅有经过证据校验的 `WorkflowSpec` 和有界 provenance 可以进入下游；完整原文只存在于进程内存。 — Phase 2
- ✓ 只有通过资格、生成、格式/安全校验和独立 Reviewer 的候选才能进入受控 catalog 发布 admission。 — Phase 3–4
- ✓ Publisher 只能创建或更新机器分支、Draft PR 和个人 reviewer 请求；生产代码没有 merge、approve、ready、默认分支写入或 ruleset 管理能力。 — Phase 4（Gate B4 实测）
- ✓ Draft PR 包含来源、commit SHA、许可证、验证、独立评审和人类控制证据，最终合并只能由人类完成。 — Phase 4
- ✓ 相同发布身份可安全复用/更新一个 Draft，并从远端状态恢复；冲突、歧义或篡改状态在写入前失败关闭。 — Phase 4

### Active

- [ ] 系统可通过每日定时任务和人工触发，使用 GitHub Search API 搜索公开仓库候选。
- [ ] 单次运行默认最多获取 100 个候选仓库，并最多让 20 个候选进入 LLM 语义分析。
- [ ] 生成前设置独立的确定性资格门，对来源证据、最少步骤数、可复用性结论、通用性和提取置信度等硬条件进行判定。
- [ ] 系统根据结构化工作流生成符合 Agent Skills 规范的目录包，以 `SKILL.md` 为核心，并可按需包含 `scripts/`、`references/` 和 `assets/`。
- [ ] 生成内容默认重新表述；仅保留必要的短片段并清晰归因，不复制来源仓库的可执行代码。
- [ ] 每个生成结果都包含来源仓库、提交 SHA、许可证和所用来源文件等 provenance 信息。
- [ ] 生成的 Skill 必须通过确定性格式检查、安全检查和来源约束检查。
- [ ] 独立 LLM Reviewer 必须在不了解生成过程内部推理的前提下评价可复用性、质量、安全性、来源完整性和发布价值。
- [ ] Reviewer 只输出结构化通过或拒绝结论、置信度、理由、缺失假设和最小修改建议，不得编辑或重写 Skill。
- [ ] SQLite 保存运行、候选、快照、阶段产物、评审和 PR 状态；敏感凭据不进入数据库或生成产物。
- [ ] MVP 必须在至少 5 个不同公开仓库上完成端到端验证，并证明重跑幂等、不会执行外部代码、不会自动合并。

### Out of Scope

- 自动合并 Pull Request — 所有进入主分支的 Skill 必须由人类审核和合并。
- 执行不受信任仓库中的代码 — 外部仓库只作为受限、只读、不可信的数据源。
- 访问未授权密钥 — 仅使用完成 GitHub 与 OpenAI 调用所需的最小权限凭据。
- 大规模向量数据库 — MVP 的规模和检索需求可由 SQLite 与确定性索引满足。
- 多租户 — MVP 面向单一受控运营环境和中央 Skill 仓库。
- Web 管理后台 — MVP 通过 GitHub Actions、日志、结构化产物和 Pull Request 完成人机协作。
- 自动修改 SkillScout 自身代码 — 生成能力仅面向目标 Skill 包。
- 自动发布到公共 Skill 市场 — MVP 的发布边界止于中央仓库 Draft PR。
- 私有仓库发现 — MVP 只处理公开 GitHub 仓库。
- 从候选仓库复制或运行可执行代码 — 即使许可证允许也不在 MVP 范围内。
- Prompt 集合、普通 SDK 或单一配置片段的泛化收录 — 缺少完整可复用工作流结构时不视为合格 Skill。

## Context

- 目标使用者是中央 Skill 仓库的维护者和 Pull Request 审核者，而不是来源仓库作者或最终 Skill 用户。
- 现有人工流程需要维护者主动寻找仓库、阅读大量不一致的文档、判断是否存在可复用工作流，再手工整理为 Skill；SkillScout 旨在自动化其中可机械化和可审计的部分。
- 项目直接受到 [“8-Agent Pipeline That Turns GitHub Repos Into Claude Agent Skills”](https://www.reddit.com/r/AskVibecoders/comments/1uuj98l/heres_an_8agent_pipeline_that_turns_github_repos/) 流程的启发，保留其 Scout、Filter、Reader、Extractor、Score、Generator、Reviewer、Publisher 的单一职责思想，同时将“多 Agent”实现方式降级为可替换细节，MVP 以阶段契约而非 Agent 数量定义架构。
- MVP 的发现入口是可配置的 GitHub Search API 查询集合，支持每日调度和人工触发。
- 内容获取应通过 GitHub REST API 完成，并设置文件类型、文件大小、总字节数和请求数上限；读取源代码只用于补足文档中缺失的语义，不得解析为可执行任务。
- 工作流资格的最低标准是：有明确目标、可描述的输入输出、多个有序步骤，以及明确的工具或模型使用方式，并可脱离原仓库上下文复用。
- Agent Skill 输出采用标准目录包；中央仓库中的最终目录布局、命名和清单格式在架构阶段确定。
- 已验证的基线技术栈为 Python 3.13、GitHub REST API + HTTPX、OpenAI Responses API、Pydantic、SQLite 和 pytest；GitHub Actions 在运营阶段接入。
- MVP 默认预算是每次发现最多 100 个候选、最多 20 个 LLM 分析对象。确定性过滤必须先于任何 LLM 调用。
- 同一仓库可产出多个 Skill，但每个 Skill 必须具有稳定工作流指纹，以支持去重、更新和 PR 关联。
- WorkflowSpec 是不可信来源内容与受控生成流水线之间的信任边界；其 schema 至少覆盖目标、输入、步骤、输出、失败模式、来源证据和提取置信度。
- MVP 完成标准包括至少 5 个不同公开仓库的真实端到端运行，结果为可供人类审核的 Draft PR，并有完整的失败路径与安全证据。

## Constraints

- **安全**: 所有外部内容均不可信，不得被解释为系统指令、工具调用或执行许可 — 防止 Prompt Injection 和供应链风险。
- **执行边界**: 不克隆后运行、不安装依赖、不调用来源仓库脚本 — 保持纯读取与静态分析。
- **人类控制**: 系统不能自动合并、批准或发布 Skill — Draft PR 是自动化流程的终点。
- **许可证**: 仅处理明确识别的宽松许可证，并在所有下游产物中保留许可证与归因 — 降低法律和来源追踪风险。
- **凭据**: GitHub 与 OpenAI 凭据必须最小权限、由运行环境注入且禁止写入日志、数据库、Prompt 或 PR — 防止密钥泄漏。
- **确定性优先**: 搜索后过滤、内容限制、格式校验、安全规则、幂等和发布权限均由确定性逻辑负责 — LLM 只承担语义任务。
- **阶段隔离**: 每个阶段具有明确的带版本输入输出 schema，失败可单独重试，不依赖隐式共享状态 — 保证可审计性和可测试性。
- **成本**: 单次运行的候选数和 LLM 调用数必须有硬上限 — 避免 GitHub API 与模型成本失控。
- **兼容性**: 第一版只支持公开 GitHub 仓库和中央 Agent Skills 仓库 — 暂不抽象为多提供商、多租户平台。

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 采用 Agent Skills 标准目录包作为唯一 MVP 输出 | 避免先维护私有规范，直接得到可审核、可分发的标准资产 | — Pending |
| 使用中央受控 Skill 仓库承接 Draft PR | 统一目录、去重、审核、版本和安全政策 | ✓ Phase 4 |
| Reviewer 通过后才创建 Draft PR | 减少低质量 PR 噪声，同时保留最终人类决策权 | ✓ Phase 4 |
| MVP 仅扫描公开 GitHub 仓库 | 简化权限模型并减少隐私与凭据风险 | — Pending |
| MVP 仅接受明确的宽松许可证 | 建立保守、确定性的法律门槛 | ✓ Phase 2 |
| 一个仓库可生成多个独立 Skill | 仓库可能包含多个可单独复用的工作流，不应被迫合并 | ✓ Phase 2（提取上限 3） |
| 每日调度并支持人工触发 | 兼顾持续发现与可控调试 | — Pending |
| 每次最多 100 个候选、20 个 LLM 分析对象 | 为 MVP 建立明确的成本与速率边界 | — Pending |
| 使用仓库、提交 SHA 和工作流指纹实现幂等 | 避免重复成本与 PR 噪声，同时允许来源更新 | ✓ Phase 4（发布身份与 revision lineage） |
| 默认重新表述来源内容且不复制可执行代码 | 减少安全、维护和版权风险，同时保留必要归因 | — Pending |
| 至少 5 个真实公开仓库通过端到端验收 | 验证系统不是仅对单一样例成立 | — Pending |
| 以阶段契约而不是固定 Agent 数量定义系统 | 保留启发流程的职责隔离，同时避免为 MVP 引入不必要的多 Agent 编排复杂度 | — Pending |
| 提取后只向下游传递 WorkflowSpec 与 provenance | 缩小 Prompt Injection 传播面，并让评分、生成和审核可独立测试 | ✓ Phase 2 |
| Reviewer 只评判、不编辑 | 避免生成者与评判者职责混淆，并保留清晰的审核证据 | ✓ Phase 3 |
| 描述符锚定本地文件系统 + 确定性原子替换 + flock 下 owner 校验 stale-temp 恢复 | 进程/主机崩溃窗口可在不重放已验证副作用的前提下修复；被拒绝的 temp 保留且 fail closed | ✓ Phase 1 |
| 内容寻址、全链校验的 SQLite 状态与不可变 resume 事件作为唯一复用权限 | 公共复用计数只能来自已验证事件链，消除重放与篡改面 | ✓ Phase 1 |
| dry-run 以能力缺失（无 remote adapter）与封闭 scope 上限架构级阻止远程写入 | 无写入不是配置开关而是结构属性；`remote_writes_attempted=0` 可验证 | ✓ Phase 1 |
| 独立 gap-evidence 权威：封闭 source 摘要集 + AST 绑定 finding 节点 + 外部 cwd record/rerun | 证据可独立重跑、fail-closed；评审/验证文档字节变化即过期，稳定后重新 record | ✓ Phase 1 |
| descriptor-less 禁止项走人工会签（UAT），honest verifier 不静默通过 | 判断级禁止项永不被自动验证吸收；由人类 countersign 后 verification 才置 passed | ✓ Phase 1 |
| 以固定 commit 与 tree-derived blob SHA 作为唯一读取权威 | 禁止 floating ref，使每个证据片段都能追溯到不变的远程内容 | ✓ Phase 2 |
| OpenAI SDK 内部重试为 0，重试权只属于流水线策略 | 保证一个语义尝试恰好一个 HTTP 请求，业务结果不被反复询问 | ✓ Phase 2 |
| 完成运行只能经过已验证链的 `find_completed_run` 复用 | 同一仓库/SHA/指纹重跑不产生新远程请求或状态转移 | ✓ Phase 2 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (start with `superpowers:using-superpowers`, then
use the applicable planning and verification skills):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (during a Superpowers-guided review):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-27 after Phase 4*
