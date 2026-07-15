# 功能研究

**项目：** SkillScout  
**研究日期：** 2026-07-15  
**目标：** 定义一个可在首版中被验证、可审核、不会越权发布的最小产品。

## 产品判断

SkillScout 的价值不是“让一个大模型浏览仓库并写文件”，而是把一个高风险的开放式任务变成可解释的候选漏斗：确定性发现和过滤缩小范围，受限 Reader 提供可追溯证据，语义提取产出唯一的信任边界，确定性评分和校验控制质量，独立 Reviewer 给出发布意见，Publisher 最终只创建 Draft PR。

架构不应绑定“正好 8 个 Agent”。真正稳定的产品边界是阶段契约；某个阶段可以是规则、普通 Python 服务或独立 LLM 调用。

## MVP 必须具备

### 1. 发现与预算控制

- 支持一组版本化 GitHub Search 查询。
- 支持每日定时运行和人工 `workflow_dispatch`。
- 单次最多接收 100 个候选，最多 20 个进入 LLM 分析。
- 保存查询、分页、rate-limit 信息、发现时间和候选来源。
- 同一仓库在一个 run 内去重；已处理相同 commit SHA 的候选直接复用结果。

### 2. 确定性过滤

- 公共、非 archived、非 fork（除非未来显式允许）、有默认分支、有 README。
- 仓库级许可证必须明确命中许可白名单。
- 按文件数量、内容预算、最近活跃度、主题/关键词和明显非 AI 工作流信号执行可解释规则。
- 每条规则输出 `pass/fail/not_applicable`、观察值和理由；LLM 不参与许可证或硬门槛判断。

### 3. 受限仓库阅读

- 固定优先级：README → docs → examples → 包清单 → 少量源代码。
- 先解析仓库 tree 元数据，再按 allowlist 取文本；拒绝二进制、超大文件、子模块、LFS pointer、压缩包和路径穿越。
- 每个 Reader 结果记录读取文件、blob SHA、内容 hash、字节/token 预算、是否读到源码和停止原因。
- 一旦证据足以判断是否存在可复用工作流就 early stop。
- 只读文本，永不安装依赖、执行脚本、构建项目或加载动态模块。

### 4. 工作流语义提取

- LLM 只回答“是否存在可复用的 AI 工作流”并把每个工作流转为严格 `WorkflowSpec`。
- 一个仓库可产出多个工作流，但每个工作流必须有独立证据和稳定 fingerprint。
- `WorkflowSpec` 至少包含目标、适用条件、输入、顺序步骤、输出、失败模式、证据引用、假设和置信度。
- 只要输出离开 Extractor，后续阶段不得再看到完整原始仓库文本。
- 结构化拒绝、schema 失败和低置信度均进入人工可诊断状态，不靠字符串猜测。

### 5. 确定性资格门槛与评分

- 在生成 Skill 前检查工作流是否足够具体、可复用、可验证、证据充分且不依赖执行未授权代码。
- 规则输出逐项解释、总分、门槛版本和拒绝理由。
- 评分规则作为版本化产品政策，可用 fixture 回归测试；不把“值不值得生成”完全交给模型。

### 6. 标准 Agent Skill 生成

- 生成符合 Agent Skills 规范的目录名和 `SKILL.md`；必要时生成 `references/` 或 `assets/`。
- MVP 只生成文档型 Skill，不生成 `scripts/` 或复制仓库中的可执行代码。
- 内容必须是改写后的通用工作流，禁止大段复制；短摘录必须携带路径与 commit SHA 归属。
- 每个 Skill 包含 provenance manifest：来源 URL、精确 commit SHA、许可证 SPDX、证据文件与 hash、生成器模型和 schema/prompt 版本。
- 稳定 slug 和 workflow fingerprint 让同一工作流更新已有 Draft PR，而不是制造重复项。

### 7. 安全与格式验证

- 运行 Agent Skills 官方验证器和自有 frontmatter/目录/引用完整性检查。
- 扫描密钥形态、外部 URL、危险命令、越权工具要求、自动下载/执行指令、Prompt Injection 残留、过长引用和来源缺失。
- 检查生成内容没有 `scripts/`，没有 vendored executable，没有仓库原文的大段近似复制。
- 校验报告必须结构化，区分 error/warning/info；任何 error 阻止 Reviewer 通过。

### 8. 独立 Reviewer

- Reviewer 是与 Extractor/Generator 分离的模型请求，不共享对话历史，不修改或重写 Skill。
- 输入只有 `WorkflowSpec`、生成的 Skill、provenance 和 validation report。
- 输出 `YES/NO`、置信度、理由、缺失假设、最小修改建议和 policy version。
- 只有确定性校验全通过且 Reviewer 给出 `YES` 才能进入 Publisher。

### 9. Draft PR 发布

- Publisher 创建或更新确定性分支，提交生成物，创建 Draft PR，并请求配置好的人类 Reviewer。
- PR 正文必须包含来源、commit、许可证、workflow fingerprint、生成/审核摘要、安全检查和明确的“需要人工审核”。
- Publisher 不能设置 auto-merge、调用 merge API、push 默认分支或把 PR 标记 ready for review。
- 失败重试先按分支、PR head 和机器可读 marker 查重，避免重复 PR。

### 10. 可恢复性、审计与 dry-run

- 每个阶段保存带 schema version、input/output hash 的结构化结果和 attempt 状态。
- 相同 `repo + commit SHA + workflow fingerprint + policy versions` 可幂等复用。
- 提供本地和 CI dry-run：完成到发布计划，但不写远程分支/PR。
- 失败可从最近成功阶段继续；人工能看到为什么候选被过滤、为何停止阅读、为何 Reviewer 拒绝。
- 使用 5 个真实公共仓库完成一次端到端验收，并包含 Prompt Injection fixture。

## 推荐的产品差异点

这些能力不是额外花哨功能，而是 SkillScout 相比一次性生成脚本的可信度来源：

| 差异点 | 用户价值 |
|---|---|
| `WorkflowSpec` 单一信任边界 | 原始仓库中的恶意指令不会自然传播给 Generator、Reviewer 或 Publisher。 |
| 可解释的决策账本 | 每个淘汰、评分、停止和发布决定都有规则版本、证据与原因。 |
| 稳定 fingerprint + 更新 Draft | 同一工作流不会反复制造 PR 噪声，可看到来源更新带来的变化。 |
| Reader early stop 指标 | 能量化“为了得出结论读了多少”，控制成本并缩小攻击面。 |
| Reviewer 只判断不改写 | 防止审核阶段悄悄引入未经再次校验的新内容。 |
| 文档型 Skill 首发 | 先证明发现与抽象质量，再承担生成可执行供应链的风险。 |

## 明确延后

- 私有仓库和企业内网源。
- 自动生成或打包 `scripts/`。
- 向量数据库、embedding 搜索和语义去重。
- 多租户、权限管理、用量计费。
- Web 管理后台。
- 多 LLM provider 编排。
- 大规模并发或事件总线。
- 自动修复 Reviewer 意见的循环。
- 自动发布到公共 Skill 市场。
- 自动修改 SkillScout 自身代码。
- 自动 merge、自动 ready-for-review 或自动批准。

## 反功能：MVP 必须拒绝

| 反功能 | 为什么危险 |
|---|---|
| clone 后执行测试来“理解”仓库 | 直接引入供应链执行风险，违反用户给定边界。 |
| 把 README 原文连同系统工具交给 Agent | Prompt Injection 可诱导泄密或执行动作。 |
| 让 LLM 判断许可证、文件大小或重复项 | 不可重复且难审计，规则足以完成。 |
| 让 Reviewer 顺手修改 Skill | 修改后的内容没有经过同一验证链。 |
| 把 Actions cache 当数据库 | 状态可能无预警丢失，幂等性无法保证。 |
| 自动化身份可绕过默认分支保护 | Draft PR 的人工门禁失去真实约束。 |
| 用固定“八个 Agent”定义系统 | 把实现形式误当成产品契约，难以测试和替换。 |

## MVP 成功指标

### 必须通过的验收门槛

- 至少 5 个公共仓库被真实读取并产生完整阶段记录。
- 至少一个合格工作流生成 Draft PR；也保留被过滤、低分、校验失败或 Reviewer 拒绝的案例。
- 对相同 commit 重跑不会创建重复工作流、分支或 PR。
- 修改相关来源后能生成新 revision，并更新对应 Draft PR。
- Prompt Injection fixture 无法触发工具、密钥访问、额外网络访问或 Publisher 越权。
- 自动化 token 实测不能向默认分支 push，也不能 merge。
- 所有 Draft PR 都包含来源、commit SHA、许可证与人类审核提示。

### 观察指标，不作为首版硬 KPI

- 每 run 的候选→读取→提取→生成→Review→Draft 漏斗。
- 每阶段延迟、错误率、重试率和 token 成本。
- Reader 平均文件数/字节数/early-stop 比例。
- 人类 Reviewer 接受率、拒绝理由和后续修改量。
- 重复工作流率与已有 Draft 更新率。

## 依赖关系

```text
Search
  └─> Deterministic Filter
        └─> Bounded Reader
              └─> Workflow Extractor
                    └─> Qualification Gate
                          └─> Skill Generator
                                └─> Validators
                                      └─> Independent Reviewer
                                            └─> Draft PR Publisher

横切能力：版本化契约、幂等键、状态/审计、预算、秘密保护、dry-run
```

## 研究来源

- [启发文档对应的 Reddit 原帖：8-Agent pipeline](https://www.reddit.com/r/AskVibecoders/comments/1uuj98l/heres_an_8agent_pipeline_that_turns_github_repos/)
- [Agent Skills specification](https://agentskills.io/specification)
- [OpenAI Agent safety](https://developers.openai.com/api/docs/guides/agent-builder-safety)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [GitHub Pull Requests API](https://docs.github.com/en/rest/pulls/pulls)

