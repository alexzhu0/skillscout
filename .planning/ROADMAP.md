# Roadmap: SkillScout

**Created:** 2026-07-16  
**Planning mode:** Vertical MVP slices  
**Milestone:** v1 — Safe discovery-to-Draft-PR MVP

## Overview

SkillScout v1 通过六个递进的纵向切片交付。第一阶段先打通可审计、可恢复且绝不产生远程副作用的流水线脊柱；随后以人工指定的单个公开仓库逐步接入真实读取、语义提取、Skill 生成、独立审核和 Draft PR。端到端路径被证明安全后，再扩大到 GitHub Search、定时运行和多候选状态管理，最后用五个真实仓库与对抗输入完成发布验收。

每个阶段结束时都有一个可运行、可观察的用户结果。阶段边界由版本化结构契约定义，不由固定数量的 Agent 或服务定义。

## Phases

- [x] **Phase 1: Auditable Dry-Run Spine** — 用确定性 fixture 打通所有阶段状态、审计、恢复和副作用防火墙。 (completed 2026-07-21)
- [x] **Phase 2: Safe Single-Repository Extraction** — 从一个指定公共仓库安全地产出 `WorkflowSpec` 或结构化拒绝。 (completed 2026-07-22)
- [x] **Phase 3: Validated Skill Candidate** — 把合格 `WorkflowSpec` 转为经过格式、安全和独立审核的本地 Skill 候选。 (completed 2026-07-23)
- [ ] **Phase 4: Controlled Draft PR** — 在平台权限硬约束下创建或更新一个可追溯 Draft PR。
- [ ] **Phase 5: Automated Discovery Operations** — 将已验证的单仓库路径扩展到定时/手动 GitHub Search 和持久状态。
- [ ] **Phase 6: Adversarial MVP Acceptance** — 用五个真实仓库、注入样本和权限 canary 证明 MVP 达标。

## Phase Details

### Phase 1: Auditable Dry-Run Spine

**Goal:** 用户可以用冻结 fixture 运行一条从候选输入到“拟发布结果”的完整流水线；所有阶段都有版本化结构结果、可恢复 checkpoint，并且 dry-run 在架构层阻止远程写入。

**Depends on:** Nothing  
**Requirements:** OPS-01, OPS-04  
**Plans:** 18/18 plans complete

- [x] 01-01-PLAN.md
- [x] 01-02-PLAN.md
- [x] 01-03-PLAN.md
- [x] 01-04-PLAN.md
- [x] 01-05-PLAN.md
- [x] 01-06-PLAN.md
- [x] 01-07-PLAN.md
- [x] 01-08-PLAN.md
- [x] 01-09-PLAN.md
- [x] 01-10-PLAN.md
- [x] 01-11-PLAN.md
- [x] 01-12-PLAN.md
- [x] 01-13-PLAN.md
- [x] 01-14-PLAN.md
- [x] 01-15-PLAN.md
- [x] 01-16-PLAN.md
- [x] 01-17-PLAN.md
- [x] 01-18-PLAN.md

**Wave 1**

- [x] `01-01-PLAN.md` — Gate-A-verified local toolchain, non-building lock discovery and Gate B approval of one canonical first-party root plus registry-only external graph.

**Wave 2** *(blocked on Wave 1 completion)*

- [x] `01-02-PLAN.md` — Safe packaged CLI Walking Skeleton with one-descriptor controls, sanitized schema-v1 errors and a real Generator-interrupted v1 freeze.

**Wave 3** *(blocked on Wave 2 completion)*

- [x] `01-03-PLAN.md` — Strict contracts, transactional interrupted-v1→v2 migration with Validators-first no-replay proof, content-addressed ledger, inspect/resume and digest-scoped retry.

**Wave 4** *(blocked on Wave 3 completion)*

- [x] `01-04-PLAN.md` — Capability firewall, expanded fail-closed boundaries and final zero-network acceptance.

**Wave 5** *(blocked on Wave 4 completion)*

- [x] `01-05-PLAN.md` — Immutable Phase-1 authority ceiling and truthful adapter-owned capability declarations.

**Wave 6** *(blocked on Wave 5 completion)*

- [x] `01-06-PLAN.md` — Bounded JSON contracts, writer/reader symmetry and complete durable lifecycle closure.

**Wave 7** *(blocked on Wave 6 completion)*

- [x] `01-07-PLAN.md` — Descriptor-anchored filesystem and SQLite persistence with crash-safe durability.

**Wave 8** *(blocked on Wave 7 completion)*

- [x] `01-08-PLAN.md` — Run-scoped result identity, exact reusable identity and A/B/A resume correctness.

**Wave 9** *(blocked on Wave 8 completion)*

- [x] `01-09-PLAN.md` — Exact SQLite schema fingerprinting and sanitized persisted diagnostics.

**Wave 10** *(blocked on Wave 9 completion)*

- [x] `01-10-PLAN.md` — Unified full-chain canonical ledger verification across migration, resume and inspect.

**Wave 11** *(blocked on Wave 10 completion)*

- [x] `01-11-PLAN.md` — Locked end-to-end acceptance and an independently verifiable evidence index.

**Wave 12** *(blocked on Wave 11 completion)*

- [x] `01-12-PLAN.md` — Truthful snapshot commit outcomes, collision-free state namespaces, and private state-file admission.

**Wave 13** *(blocked on Wave 12 completion)*

- [x] `01-13-PLAN.md` — Immutable resume-event authority with explicit zero-prefix crash semantics.

**Wave 14** *(blocked on Wave 13 completion)*

- [x] `01-14-PLAN.md` — Full-chain resume-event verification and tamper-proof reuse projections.
- [x] `01-15-PLAN.md` — Non-echoing CLI rejection and policy-correct recovery from unexpected processor failures.

**Wave 15** *(blocked on Wave 14 completion)*

- [x] `01-16-PLAN.md` — Independently rerunnable evidence authority and final seven-finding acceptance.

**Wave 16** *(blocked on Wave 15 completion)*

- [ ] `01-17-PLAN.md` — Coordinated stale-temp crash recovery across state, backup, manifest, and publication-plan writes with a killed-writer no-prefix-replay regression.

**Wave 17** *(blocked on Wave 16 completion)*

- [ ] `01-18-PLAN.md` — Fixture-complete evidence authority, current two-finding map, and freshly recorded independently rerun evidence.

**Success Criteria:**

1. 一个确定性 fixture 能依次经过 Scout、Filter、Reader、Extractor、Qualifier、Generator、Validators、Reviewer 和 Publisher plan，产生完整 stage ledger。
2. 每个 stage result 都包含 schema version、稳定 subject ID、input/output hash、时间、attempt 及适用的模型/提示词/政策版本。
3. 在任意阶段注入暂时性失败后，重新运行可以从最近成功 checkpoint 恢复，而不是重复已完成副作用。
4. dry-run 使用显式无写入 adapter；即使发布结果为 approved，也只能生成 publication plan，不能创建分支或 PR。
5. 契约测试证明相同 fixture 和版本产生稳定 hash，非法状态跃迁或 schema 不兼容会被拒绝。

### Phase 2: Safe Single-Repository Extraction

**Goal:** 用户提供一个公开 GitHub 仓库，系统固定 commit、执行确定性过滤和有预算阅读，并返回最多三个有证据的 `WorkflowSpec` 或清晰的过滤/无工作流结论；任何候选内容都不会被执行或传入下游。

**Depends on:** Phase 1  
**Requirements:** FILT-01, FILT-02, FILT-03, READ-01, READ-02, READ-03, READ-04, READ-05, READ-06, EXTR-01, EXTR-02, EXTR-03, EXTR-04, SEC-01  
**Plans:** 4/4 plans complete

- [x] 02-01-PLAN.md
- [x] 02-02-PLAN.md
- [x] 02-03-PLAN.md
- [x] 02-04-PLAN.md

**Success Criteria:**

1. 对一个人工指定仓库，系统只通过 GitHub REST 读取固定 SHA 的允许文本，并按 README → docs → examples → 包清单 → 源码顺序及默认预算 early stop。
2. 每个确定性过滤决定包含规则、观察值和理由；不明确许可证或其他硬门槛不会调用 LLM。
3. Extractor 使用无工具、`store=false` 的严格结构化请求，能输出 0–3 个符合契约的 `WorkflowSpec`，并把拒绝/schema 失败保存为可诊断结果。
4. 每个工作流的关键目标和步骤都有来源路径、blob/content hash 和必要短证据；fingerprint 对相同规范化语义稳定。
5. Prompt Injection fixture 无法触发工具、网络动作、密钥访问或跨越 `WorkflowSpec`；Phase 2 输出中可以证明 Generator 侧没有完整原始仓库内容。
6. 测试证明流程不会 clone、安装、构建、import、运行示例，且会拒绝二进制、超预算、子模块、LFS 和路径异常。

### Phase 3: Validated Skill Candidate

**Goal:** 用户可以把已提取工作流转换为标准、文档型、来源清晰的本地 Agent Skill；系统能解释资格、格式、安全和独立 Reviewer 的每个结论。

**Depends on:** Phase 2  
**Requirements:** QUAL-01, QUAL-02, GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, VAL-01, VAL-02, VAL-03, REV-01, REV-02, REV-03  
**Plans:** 14/14 plans complete

Plans:
**Wave 1**

- [x] 03-01-PLAN.md — Decide Gate A3 before resolving the anomalous official-validator candidate.

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-02-PLAN.md — Resolve the exact skills-ref graph without installing or executing package code.

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 03-03-PLAN.md — Decide Gate B3 for exact lock bytes and all transitive artifacts.

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 03-04-PLAN.md — Enforce the approved lock identity before every dependency-backed command.

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 03-05-PLAN.md — Define complete execution authority and exact lineage/binding rules.

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 03-06-PLAN.md — Reverify one completed Phase 2 workflow through a read-only pre-run source barrier.
- [x] 03-07-PLAN.md — Implement deterministic 100-point workflow qualification and hard failures.

**Wave 7** *(blocked on Wave 6 completion)*

- [x] 03-08-PLAN.md — Generate and freeze provenance-complete documentation-only Skill packages.

**Wave 8** *(blocked on Wave 7 completion)*

- [x] 03-09-PLAN.md — Run the approved official validator plus deterministic safety/source checks.

**Wave 9** *(blocked on Wave 8 completion)*

- [x] 03-10-PLAN.md — Add independent judge-only review, exact eligibility, and external attestations.

**Wave 10** *(blocked on Wave 9 completion)*

- [x] 03-11-PLAN.md — Persist an isolated Phase 3 ledger with byte-stable zero-side-effect reuse.

**Wave 11** *(blocked on Wave 10 completion)*

- [x] 03-12-PLAN.md — Orchestrate the exact Phase 3 stage, terminal, resume, and budget cascade.

**Wave 12** *(blocked on Wave 11 completion)*

- [x] 03-13-PLAN.md — Deliver the strict local build-candidate CLI and public security tests.

**Wave 13** *(blocked on Wave 12 completion)*

- [x] 03-14-PLAN.md — Enforce final import, package, provenance, seam, and Nyquist acceptance gates.

**Success Criteria:**

1. 确定性资格规则在生成前给出逐项检查、75/100 默认门槛、硬性失败和版本化解释。
2. 通过资格门槛的工作流生成符合 Agent Skills 规范的稳定目录与 `SKILL.md`，必要时使用单层 `references/`/`assets/`，但绝不生成 `scripts/`、二进制或可执行位。
3. Skill 内容是对工作流的通用改写；provenance 完整包含来源仓库、repo ID、commit SHA、许可证、证据 hash 以及 schema/prompt/policy/model 版本。
4. 官方 validator 与自有安全/来源检查均产生结构化报告；secret、危险执行、越权工具、注入残留、缺失来源或过度复制会阻止通过。
5. Reviewer 使用新的独立上下文，只读取 WorkflowSpec、artifact、provenance 和 Validation Report，输出 YES/NO、置信度、理由、缺失假设和最小修改建议，且无法返回修改文件。
6. 相同输入和版本可稳定复用 artifact；validation error 或 Reviewer NO/低置信度只能形成可审计拒绝，不能进入 publication plan。

### Phase 4: Controlled Draft PR

**Goal:** 对一个通过全部门禁的 Skill，系统只能在受控 catalog 中创建或更新机器分支和 Draft PR，并请求人类审核；平台权限实测禁止自动化身份写默认分支或 merge。

**Depends on:** Phase 3  
**Requirements:** PUB-01, PUB-02, PUB-03, PUB-04, PUB-05, SEC-02  
**Plans:** 11 plans

Plans:

**Wave 1**

- [ ] `04-01-PLAN.md` — Freeze canonical admission, deterministic Draft metadata, and negative-capability tests before implementation.
- [ ] `04-02-PLAN.md` — Freeze bounded GitHub transport, crash-recovery, ambiguity, and opt-in live-canary fixtures/tests.
- [ ] `04-07-PLAN.md` — Audit exact checkout and GitHub App-token action commits without installing or executing them.

**Wave 2** *(blocked on Wave 1 prerequisites)*

- [ ] `04-03-PLAN.md` — Implement pure catalog-bound publication authority, exact Phase 3 admission, marker, and PR rendering.
- [ ] `04-08-PLAN.md` — Obtain non-auto-approvable human approval for the exact audited workflow action identities.

**Wave 3** *(blocked on publication domain and transport fixtures)*

- [ ] `04-04-PLAN.md` — Implement the separate closed GitHub REMOTE_WRITE adapter and forbidden-surface proofs.

**Wave 4** *(blocked on domain and adapter)*

- [ ] `04-05-PLAN.md` — Implement durable checkpoints, reconcile-first recovery, and idempotent Draft publication.

**Wave 5** *(blocked on recovery application)*

- [ ] `04-06-PLAN.md` — Compose late-token publication and expose the closed `publish-candidate` CLI.

**Wave 6** *(blocked on CLI and action approval)*

- [ ] `04-09-PLAN.md` — Add the protected pinned Actions workflow and causal live-canary probes.

**Wave 7** *(blocked on workflow)*

- [ ] `04-10-PLAN.md` — Run the non-auto-approvable live ruleset/App permission canary and separate-authority cleanup.

**Wave 8** *(blocked on live evidence)*

- [ ] `04-11-PLAN.md` — Finalize the exact validation map, independent acceptance inspector, and locked release chain.

**Success Criteria:**

1. 短期 GitHub App installation token 只可在配置的 catalog 创建/更新允许前缀的分支、提交已验证 manifest 中的文件、创建 Draft PR 和请求指定人类 reviewer/team。
2. Draft PR 正文包含来源、精确 SHA、许可证、fingerprint、证据、资格、安全/格式检查、独立审核与明确人工审核提示。
3. 重复发布同一 slug 会更新同一 Draft PR；在本地 publication state 缺失时，可通过远端 head 和机器 marker 恢复，而不创建重复 PR。
4. 如果已有 PR 不是 Draft、head 出现不可安全覆盖的人类冲突，或目标文件不在验证 manifest 中，Publisher 停止并给出人工处理结果。
5. catalog ruleset canary 实测自动化身份无法 push 默认分支、merge、approve、标记 ready、修改 ruleset 或访问未授权 secrets。
6. Publisher adapter 和请求 allowlist 不提供 merge/auto-merge/administration 能力；候选数据不被直接插值到 shell。

### Phase 5: Automated Discovery Operations

**Goal:** 用户可以通过每日任务或手动运行，从 GitHub Search 自动发现有限数量候选，并让已验证的端到端路径在临时 Actions runner 上保持可恢复、可审计和幂等。

**Depends on:** Phase 4  
**Requirements:** DISC-01, DISC-02, DISC-03, OPS-02, OPS-03  
**Plans:** To be created with phase planning

**Success Criteria:**

1. 版本化查询集支持 daily schedule 与 `workflow_dispatch`，每 run 硬限制 100 个去重候选、20 个 LLM 候选，并记录 query、cursor、来源和 rate-limit 数据。
2. Search 候选自动进入已经验证的过滤→读取→提取→资格→生成→校验→审核→Draft PR 路径，业务拒绝与暂时性 API 错误保持不同状态。
3. SQLite checkpoint 和裁剪后的 JSON manifests 保存到专用 `skillscout-state` 分支；SQLite integrity/rebuild 测试证明状态可从 JSON 恢复。
4. schedule 与手动生产运行共享单一 concurrency group 且不取消进行中的 run；state push 使用远端 head 检查并能安全处理冲突。
5. runner、日志、state branch、Actions artifact、模型请求和 PR 均不持久化完整仓库原文、授权头或密钥。
6. GitHub rate-limit、OpenAI 暂时性错误和 job 中断具有有限重试与恢复证据，不会突破候选/LLM 预算或制造重复 Draft。

### Phase 6: Adversarial MVP Acceptance

**Goal:** 人类审核者可以基于一套可重复的真实仓库与对抗验收报告，确认 SkillScout 满足价值、安全、幂等和权限边界，并至少审核一个真实 Draft PR。

**Depends on:** Phase 5  
**Requirements:** TEST-01, TEST-02, TEST-03, TEST-04  
**Plans:** To be created with phase planning

**Success Criteria:**

1. 至少 5 个固定 commit SHA 的真实公共仓库完成端到端运行，保留候选漏斗、读取预算、token/延迟、各阶段决策和最终状态。
2. 验收集明确覆盖成功生成、确定性过滤、资格低分、格式/安全失败、Reviewer 拒绝、多工作流仓库及多类 Prompt Injection。
3. 对相同 repo/SHA/fingerprint/policy 重跑不产生重复 WorkflowSpec、Skill、分支或 PR；修改相关来源后重新评估并更新对应 Draft。
4. 至少一个符合门禁的 Skill 创建真实 Draft PR 并请求人类审核；最终是否合并完全由人类决定。
5. live canary 再次证明自动化身份无法写默认分支、merge、approve、ready 或读取未授权 secrets；日志和输出通过 secret scan。
6. MVP 报告列出所有 44 条需求的验证证据、遗留 warning、已知限制和是否满足发布标准。

## Requirement Mapping

| Phase | Primary requirements | Count |
|---|---|---:|
| Phase 1 | OPS-01, OPS-04 | 2 |
| Phase 2 | FILT-01..03, READ-01..06, EXTR-01..04, SEC-01 | 14 |
| Phase 3 | QUAL-01..02, GEN-01..05, VAL-01..03, REV-01..03 | 13 |
| Phase 4 | PUB-01..05, SEC-02 | 6 |
| Phase 5 | DISC-01..03, OPS-02..03 | 5 |
| Phase 6 | TEST-01..04 | 4 |
| **Total** | **All v1 requirements** | **44** |

## Progress

| Phase | Status | Requirements | Completed |
|---|---|---:|---:|
| 1. Auditable Dry-Run Spine | Complete    | 2 | 2026-07-21 |
| 2. Safe Single-Repository Extraction | Complete | 14 | 2026-07-22 |
| 3. Validated Skill Candidate | 14/14 | Complete   | 2026-07-23 |
| 4. Controlled Draft PR | Not started | 6 | 0/6 |
| 5. Automated Discovery Operations | Not started | 5 | 0/5 |
| 6. Adversarial MVP Acceptance | Not started | 4 | 0/4 |

## Milestone Exit Criteria

SkillScout v1 只有在以下条件同时成立时才算完成：

- 44 条 v1 requirements 全部具有验证证据。
- 五个真实公共仓库通过端到端验收，包含通过和拒绝路径。
- 至少一个真实 Draft PR 已创建并交由人类审核。
- 相同输入重跑具备端到端幂等性。
- Prompt Injection、secret scan、未授权执行和 Publisher 权限 canary 全部通过。
- 自动化身份在 GitHub 平台层无法自动 merge 或写默认分支。

---
*Roadmap approved: 2026-07-16*  
*Ready for Phase 1 discussion and planning*
