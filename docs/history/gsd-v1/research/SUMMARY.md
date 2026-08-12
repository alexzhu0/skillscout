# SkillScout 项目研究摘要

**研究日期：** 2026-07-15  
**研究范围：** Agent Skills 标准、GitHub REST/Actions、OpenAI Responses API、安全边界、MVP 功能与持久化架构  
**总体结论：** 可行，但首版成败取决于把“外部文本不可信”和“人工合并不可绕过”落实为硬边界，而不是提示词约定。

## 执行摘要

SkillScout 应构建为 Python 3.13 的模块化单体 CLI/worker，在 GitHub Actions 中每日和手动运行。系统由显式阶段契约串联：Scout、Filter、Reader、Extractor、Qualifier、Generator、Validators、Reviewer、Publisher。只有 Extractor、Generator、Reviewer 使用 LLM；其余决策尽可能确定性化。

最重要的设计决定是把 `WorkflowSpec` 设为信任边界。Reader 读取的 README、docs、examples、包清单与少量源码都是不可信输入，只允许 Extractor 消费；一旦通过严格 schema 提取，后续 Generator、Reviewer 与 Publisher 不再接触完整原文。所有模型调用无工具、无代码执行、`store=false`，且 Reviewer 是独立请求，只判断、不改写。

MVP 生成符合 Agent Skills 规范的文档型 Skill，但禁止生成 `scripts/`。只有许可证明确在 MIT/Apache-2.0/BSD 白名单、确定性资格门槛通过、格式/安全校验无 error、独立 Reviewer 给出 YES 的结果，才可进入 Publisher。Publisher 只能创建或更新机器分支、创建 Draft PR、请求人类 Reviewer；默认分支 ruleset 和 GitHub App 权限必须让 direct push/merge 在平台层失败。

## 推荐范围

### 首版包含

- GitHub Search 查询集、每日 schedule 和手动触发。
- 每 run 最多 100 候选、20 个 LLM 分析。
- 可解释的确定性过滤和严格许可证白名单。
- 按优先级、有预算、可 early stop 的 API 文本读取。
- 一仓库多 `WorkflowSpec`、证据引用和稳定 fingerprint。
- 生成前确定性资格评分。
- Agent Skills 标准化生成与完整 provenance。
- 官方格式验证、自有安全/归属/相似度检查。
- 独立 Reviewer 的结构化 YES/NO 判断。
- Draft PR 创建/更新与人类 Reviewer 请求。
- SQLite + JSON 审计、幂等、恢复、dry-run、5 个真实仓库验收。

### 首版明确不含

- 自动 merge、自动 ready-for-review、自动批准。
- 执行或安装候选仓库代码。
- 生成 Skill `scripts/`。
- 私有仓库、向量数据库、多租户、Web UI、多 provider。
- 自动修复 Reviewer 意见、自动修改自身、公共市场发布。

## 推荐技术选择

| 领域 | 推荐 |
|---|---|
| Runtime | Python 3.13，部署锁具体 patch |
| GitHub | REST API + HTTPX，读取固定 commit SHA |
| AI | OpenAI Responses API + strict Structured Outputs + Pydantic |
| 默认模型 | 配置化；MVP 基线 `gpt-5.6-terra`，生产评测后锁可用 snapshot |
| 状态 | stdlib SQLite + 版本化 JSON manifests |
| 自动化 | GitHub Actions，schedule + workflow_dispatch + 单并发组 |
| 跨仓库发布身份 | 最小权限 GitHub App 短期 installation token |
| Skill 校验 | 官方 `skills-ref validate` + 自有安全政策 |
| 测试 | pytest；fixture、契约、对抗、安全、幂等和 live canary |

Python 3.12 已进入 security-only，绿地项目选择 3.13 可获得更长支持期。OpenAI Structured Outputs 与 Pydantic 适合版本化阶段契约；GitHub REST 已覆盖 MVP 所需端点。详细依据见 [STACK.md](./STACK.md)。

## 推荐架构

```text
GitHub Search
     │
     ▼
Deterministic Filter ──reject──> Audit
     │
     ▼
Bounded Reader (untrusted raw text)
     │
     ▼
LLM Extractor ──strict schema──> WorkflowSpec  ◀── trust boundary
                                      │
                                      ▼
                         Deterministic Qualifier
                                      │
                                      ▼
                              LLM Generator
                                      │
                                      ▼
                         Format + Safety Validators
                                      │
                                      ▼
                         Independent LLM Reviewer
                                      │ YES
                                      ▼
                  Branch + Draft PR + Human Reviewer
                                      │
                               human merge only
```

这是一个可测试的阶段流水线，而不是必须部署成八个自治 Agent。阶段以 Pydantic/JSON 契约连接，provider 通过 adapters 隔离。SQLite 负责查询和事务状态，结构化 JSON 负责审计与重建。

## 持久化的关键折中

GitHub-hosted runner 是临时环境，因此本地 SQLite 不能跨运行自然保留；Actions cache 和 artifact 也不具备 canonical state 的可靠性。MVP 推荐在自动化仓库的专用 `skillscout-state` 分支保存 SQLite checkpoint 和裁剪后的 JSON manifests，并用单一 concurrency group 串行生产运行。完整外部仓库正文不持久化。

这是一项有退出条件的 MVP 折中：当 DB 超过 100 MB、吞吐超过首版 10 倍、需要并发 worker，或状态 push 成为主要故障源时，将 state adapter 迁移到托管数据库/对象存储。领域契约不随之变化。详细设计见 [ARCHITECTURE.md](./ARCHITECTURE.md)。

## 核心数据模型

数据链为：

```text
Run
 └─ SearchQuery
     └─ CandidateRepository
         └─ RepositoryRevision (fixed commit SHA + license)
             ├─ FilterDecision
             └─ ReadSnapshot
                 └─ SourceDocument references
                     └─ WorkflowSpec
                         └─ QualificationDecision
                             └─ SkillArtifact
                                 └─ ValidationReport
                                     └─ ReviewDecision
                                         └─ PublicationRecord

每个处理节点另有 StageAttempt，记录重试、错误、请求 ID、token 与 artifact hash。
```

关键唯一约束：

- `RepositoryRevision`: `(github_repo_id, commit_sha)`。
- `WorkflowSpec`: `(revision_id, workflow_fingerprint)`。
- `PublicationRecord`: `(target_catalog_repo, skill_slug)` 的唯一活动 Draft。
- 每个 stage result：`input_hash + stage/schema/policy/prompt version`。

来源仓库 URL、精确 SHA、许可证、证据路径与 blob/content hash 必须贯穿到 Skill provenance 和 Draft PR。

## 最高优先级风险

1. **Prompt Injection 跨阶段传播。** 用无工具模型、低优先级不可信输入、严格 `WorkflowSpec` 和 raw-text 断流控制。
2. **候选代码被执行。** 只通过 API 读文本，不 clone/install/import/build；MVP 不生成 scripts。
3. **Publisher 权限过大。** 用 ruleset 和 GitHub App 硬限制默认分支/merge，不依赖模型承诺。
4. **密钥泄露。** secrets 只存在 adapter 边界，日志/状态/PR 都按字段 allowlist 并扫描。
5. **许可证误判。** 只接受明确单一的硬白名单 SPDX；不明或冲突直接拒绝。
6. **状态丢失导致重复 PR。** state branch + JSON rebuild + 远端 PR marker 双重恢复。
7. **Reviewer 伪独立。** 新上下文、无 raw source、只判断不改写，且不能覆盖确定性错误。
8. **无界读取和成本失控。** 100/20 run 预算、文件/字节/token 上限和 early stop。

完整风险、预警和验收控制见 [PITFALLS.md](./PITFALLS.md)。

## 建议阶段路线

研究建议把 MVP 拆成可独立验收的纵向阶段；最终 ROADMAP 仍需在需求确认后生成。

### Phase 1：可信契约与只读发现

建立领域 schema、run/state、GitHub Search/License/固定 SHA、确定性过滤、预算与审计。验收点是能解释 100 个以内候选为何进入或退出，不调用 LLM。

### Phase 2：受限阅读与工作流提取

实现 Reader 优先级、early stop、文件预算、Prompt Injection 隔离和 strict `WorkflowSpec`。验收点是对固定 fixture 只读取允许文本，多个工作流可独立提取，raw source 不进入下游。

### Phase 3：资格、生成与验证

实现确定性评分、Agent Skill 文档型生成、provenance、官方格式验证和自有安全检查。验收点是合格 artifact 可重复生成，不含 scripts/秘密/大段复制。

### Phase 4：独立审核与安全发布

实现独立 Reviewer、幂等 Draft PR、GitHub App 最小权限、ruleset canary 与失败恢复。验收点是只能创建/更新 Draft，不能 push 默认分支或 merge。

### Phase 5：自动化与真实 MVP 验收

接入 daily/manual Actions、state branch checkpoint、5 个真实仓库、成本/漏斗指标和端到端 dry-run/live canary。验收点是重复运行幂等，至少一条真实 Draft 流程完结，拒绝案例同样有完整证据。

## 需要在需求阶段锁定的政策值

研究已确定方向，但以下具体参数应作为版本化 policy，而不是散落在代码中：

- Search 查询集合和最低活跃度/仓库信号。
- Reader 单目录项、单文件字节、累计字节和 token 上限。
- 每仓库最多提取的工作流数量。
- Qualification 评分项、阈值和最低证据数。
- 允许的短摘录长度与相似度阈值。
- Reviewer YES 的最低置信度。
- 人类 reviewer/team、目标 catalog repo、状态保留期。

如果用户不另行指定，需求阶段应采用研究文档中的推荐保守默认值，并允许配置但不允许单次运行扩大到组织上限之外。

## 研究来源

- [Agent Skills specification](https://agentskills.io/specification)
- [Agent Skills GitHub repository](https://github.com/agentskills/agentskills)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI Agent safety](https://developers.openai.com/api/docs/guides/agent-builder-safety)
- [OpenAI API data controls](https://developers.openai.com/api/docs/guides/your-data)
- [GitHub Repository contents API](https://docs.github.com/en/rest/repos/contents)
- [GitHub Licenses API](https://docs.github.com/en/rest/licenses)
- [GitHub Pull Requests API](https://docs.github.com/en/rest/pulls/pulls)
- [GitHub Actions workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- [GitHub Actions security: script injections](https://docs.github.com/en/actions/concepts/security/script-injections)
- [启发文档对应原帖](https://www.reddit.com/r/AskVibecoders/comments/1uuj98l/heres_an_8agent_pipeline_that_turns_github_repos/)

## 最终建议

进入需求阶段时，按本研究的推荐范围锁定 MVP，不扩大到脚本生成、私有仓库或自动修复循环。先证明三件事：系统能从少量真实仓库稳定提取有用工作流；恶意或模糊内容无法越过结构化与权限边界；通过审核的产物只会成为需要人类决定的 Draft PR。

