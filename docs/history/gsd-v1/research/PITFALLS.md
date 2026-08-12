# 风险与陷阱研究

**项目：** SkillScout  
**研究日期：** 2026-07-15  
**原则：** 外部仓库、模型输出和远程 API 响应都可能失败或恶意；安全门禁必须由数据边界和权限系统实现。

## 风险分级

| 等级 | 含义 |
|---|---|
| P0 | 可导致密钥泄露、执行不可信代码、未经人工合并/发布，或系统性供应链污染；发布前必须有硬防护和测试。 |
| P1 | 可导致重复 PR、错误归属、不可恢复状态、显著成本失控或大量低质量 Skill；MVP 必须处理。 |
| P2 | 可造成运维摩擦、精度下降或未来迁移成本；MVP 记录并设置边界。 |

## P0：Prompt Injection 穿透流水线

### 失败方式

README 或示例伪装成项目说明，实际要求模型忽略指令、读取环境变量、调用工具、修改 PR 内容或泄露别的仓库数据。如果原文被连续传给 Generator、Reviewer 或 Publisher，攻击指令可以跨阶段累积权威。

### 防护

- 外部文本永远是低优先级 untrusted input，不拼进 developer message。
- 模型调用完全无 tools；凭据不在模型进程的可见输入中。
- Reader 限制文件类型、大小、总预算和源码读取。
- Extractor 只可输出严格 `WorkflowSpec`；schema 不允许 URL、命令或任意“下一步工具调用”字段自由传播。
- Extractor 后删除/隔离原始正文；Generator/Reviewer 只看结构化字段和短证据。
- 对模型输出再次执行确定性安全策略；Reviewer 不能覆盖 error。
- 建立持续对抗 fixture，包括显式、隐写、嵌套引用和“系统消息”伪装。

OpenAI 明确指出 Prompt Injection 可能造成数据泄漏或非预期动作，建议隔离不可信文本、使用结构化输出和人工审批。参考 [Agent safety](https://developers.openai.com/api/docs/guides/agent-builder-safety) 与 [Safety best practices](https://developers.openai.com/api/docs/guides/safety-best-practices)。

### 预警信号

- WorkflowSpec 出现与工作流无关的网络地址、密钥变量、系统指令或发布动作。
- 不同仓库提取结果出现相同异常句式。
- Generator 请求使用任何 tool，或 Reviewer 输出包含替换文件。

## P0：不可信代码被执行

### 失败方式

为了“更理解项目”而 clone、安装依赖、运行示例、import 包、执行 build hook，或让 validator 执行生成的 `scripts/`。即使仓库是热门开源项目，也不构成执行授权。

### 防护

- 仅用 GitHub API 按 SHA 读取允许的文本 blob；不 clone、不解压 release、不安装仓库依赖。
- package manifest 只作为文本解析；拒绝 lockfile 中嵌入的脚本语义被执行。
- MVP 生成器禁止输出 `scripts/`。
- 验证器只解析文本/目录，不运行 Skill 指令。
- CI job 不把仓库内容写入可执行路径，不用 `source`/`eval`，不将文件名插值为 shell。

### 预警信号

- 依赖安装命令的参数来自候选仓库。
- 测试日志出现候选项目自己的构建脚本。
- 生成 artifact 包含可执行位、shebang 或二进制。

## P0：Publisher 越权或自动合并

### 失败方式

仅靠应用代码中的 `draft=true`，但 token 实际能 push 默认分支、绕过 ruleset、启用 auto-merge 或调用 merge endpoint。一处 bug 或注入就能绕过人工门禁。

### 防护

- 默认分支 ruleset 要求人类审批，GitHub App 不可 bypass。
- App 只获得目标仓库必要的 Contents/PR 权限，使用短期 installation token。
- Publisher adapter 只实现白名单 API；不实现 merge、ruleset、secrets、workflow dispatch 写操作。
- live canary 测试断言默认分支 push 和 merge 会被 GitHub 拒绝。
- Draft PR 请求人类 Reviewer，机器不能标记 ready 或 approve。

GitHub PR API 支持 Draft，但“永不自动合并”仍需要权限层保证。参考 [Pull Requests API](https://docs.github.com/en/rest/pulls/pulls)。

## P0：Secrets 通过日志、PR 或模型泄露

### 失败方式

异常对象包含 Authorization header，模型输入携带环境变量，完整 API 响应落入 artifact，或攻击文本诱导把秘密写到 Skill/PR。GitHub 的日志脱敏无法覆盖所有编码或拼接形式。

### 防护

- secret 只在 adapter 边界读取，不进入领域对象。
- 结构化日志显式 allowlist 字段；禁记 request/response headers 和原始异常 body。
- 模型请求只含必要文本，`store=false`；不含任何 GitHub/OpenAI secret。
- PR、state JSON、artifact 在写入前执行 secret-pattern 扫描。
- 优先 GitHub App 短期 token，定期轮换 OpenAI/GitHub 凭据。
- Actions 环境与权限最小化；第三方 Action 锁完整 SHA。

GitHub 也提醒自动 redaction 不是完整保障。参考 [Using secrets in GitHub Actions](https://docs.github.com/en/actions/concepts/security/secrets)。

## P1：许可证判断过度自信

### 失败方式

Licenses API 返回 `NOASSERTION`，仓库存在多个 LICENSE，子目录/示例使用不同许可，或 README 声明与根许可证冲突。系统仍生成看似“MIT”的 Skill，造成归属和合规风险。

### 防护

- MVP 只接受明确、单一、仓库级 SPDX 命中硬白名单。
- 对 `NOASSERTION`、null、多许可证表达式、冲突声明一律拒绝，不让 LLM推断。
- provenance 保留 API 结果、LICENSE blob SHA/content hash 和 commit SHA。
- 生成内容改写，不复制源码；短摘录带路径归属。
- 在 PR 中明确这是自动化许可证检测，不是法律意见，最终由人类审核。

GitHub 的 Licensee 只匹配仓库许可证，并不穷尽依赖或文档许可。参考 [Licenses API](https://docs.github.com/en/rest/licenses)。

## P1：Reader 无界读取导致成本与攻击面膨胀

### 失败方式

大型 monorepo、生成文档、数千 examples 或超大 README 使 API 调用、token 和等待时间失控；更多原文也增加注入概率。

### 防护

- 单 run 候选上限 100，LLM 候选上限 20。
- 目录、文件、单文件字节、累计字节和 token 都有硬预算。
- 固定优先级并 early stop；Reader 输出停止原因。
- Contents API 平台上限不是产品预算，SkillScout 使用显著更低的自有上限。
- 超预算是结构化业务结果，不静默截断后声称“已完整阅读”。

参考 [Repository contents API](https://docs.github.com/en/rest/repos/contents)。

## P1：GitHub API 限流与搜索偏差

### 失败方式

Search 结果受查询、排序和索引时延影响；大量 Contents 请求触发 primary/secondary rate limit。简单重试可能加重限流或重复计费。

### 防护

- 保存 query、cursor、GitHub request ID 和 rate-limit headers。
- 对 Search/Contents 分别预算；尊重 `Retry-After` 和 reset time，指数退避加抖动。
- 查询集合版本化，按语言/主题分桶，避免 stars 排序导致只发现成熟热门仓库。
- 不宣称“扫描了整个 GitHub”；产品语义是“从当前查询策略发现候选”。
- 429/5xx 是可重试 attempt，不改变候选资格结果。

参考 [GitHub REST API rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)。

## P1：SQLite 在临时 runner 上丢失或损坏

### 失败方式

数据库只存在 GitHub-hosted runner 本地；job 结束即丢失。或者依赖 cache 恢复，cache 被淘汰后系统重复创建 PR。多个运行同时 push 二进制 DB 也会冲突。

### 防护

- 专用 state branch 保存 checkpoint 和可重建 JSON manifests。
- 单 production concurrency group 串行化，禁止 cancel-in-progress。
- JSON hash 验证与 SQLite integrity check；SQLite 可从清单重建。
- 远端 PR marker 作为发布幂等的第二事实来源。
- 设置 DB 大小和迁移阈值；不把 state branch 折中冒充长期架构。

GitHub-hosted runner 是临时环境，cache/artifact 都不提供永久状态保证。参考 [GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)、[Dependency caching](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching) 与 [Workflow artifacts](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts)。

## P1：幂等键设计错误导致重复或错误覆盖

### 失败方式

只用仓库 URL 会忽略 commit 变化；只用模型标题会因措辞变化重复；只用 slug 会把同仓库不同工作流覆盖；本地状态丢失后创建第二个 PR。

### 防护

- 身份分层：GitHub repo ID → commit SHA → workflow semantic fingerprint → artifact hash。
- fingerprint 算法和规范化规则版本化。
- 发布键为目标仓库 + skill slug，PR body 存机器 marker。
- 更新前校验 PR 仍是 Draft、head 属于机器分支、没有不可安全覆盖的人类冲突。
- 通过性质测试验证相同输入稳定、无关措辞变更不分裂、语义变化能区分。

## P1：Reviewer 不是独立门禁

### 失败方式

Reviewer 复用 Generator 对话历史、看到完整原文、被要求“顺手改好”，或其 YES 覆盖确定性 validator error。它会成为同一偏差的第二次表述，而不是独立检查。

### 防护

- 新请求、新上下文、独立 prompt/version；输入只含 spec、artifact、validation/provenance。
- Reviewer 只能输出判断与建议，schema 无文件内容字段。
- 确定性 error 直接阻止 Reviewer/Publisher。
- 保存 Reviewer 模型与置信度，建立人类接受率评测。
- MVP 不做自动 Reviewer→Generator 修复循环。

## P1：生成内容过度复制或证据不足

### 失败方式

Skill 基本是 README 改名，包含大段版权文本/代码；反之又可能生成来源没有支持的步骤，形成“漂亮但虚构”的工作流。

### 防护

- 每个关键步骤必须关联 evidence ref；无证据的推断标为 assumption 或拒绝。
- 禁止复制可执行代码；短摘录长度和累计比例设硬限制。
- 比较生成文本与已读来源的 n-gram/片段相似度，超阈值报错或人工复核。
- provenance manifest 和 PR 正文列出来源文件、SHA、许可证。
- Reviewer 检查忠实性、可复用性和未声明假设，但不替代相似度规则。

## P1：Actions 表达式注入

### 失败方式

把仓库名、路径、PR title 或 issue body 直接插入 `run:` shell，特殊字符导致命令执行。

### 防护

- 不在 shell 中展开不可信 GitHub context；先放到环境变量，再由参数数组消费。
- 尽量让 Python 通过 API 处理字符串，不构造 shell 命令。
- 发布分支、slug、文件路径严格正则化并拒绝异常值。
- 第三方 Action 锁完整 SHA，workflow permissions 最小。

参考 [GitHub Actions script injections](https://docs.github.com/en/actions/concepts/security/script-injections)。

## P2：Agent Skills 格式表面合规但不可用

### 失败方式

只通过 YAML 语法，却出现 name 与目录不一致、description 不说明触发时机、SKILL.md 过长、引用多层嵌套、链接断裂或 instructions 含糊。

### 防护

- 官方 validator + 自有语义/可用性规则双重检查。
- 按 progressive disclosure 组织：frontmatter 简短，SKILL.md 聚焦，references 一层深度。
- name、description、目录、资源路径和 provenance 均有契约测试。
- Reviewer 判断是否能让目标 Agent 在合理上下文内实际复用。

参考 [Agent Skills specification](https://agentskills.io/specification)。

## P2：模型和规则漂移使结果不可比较

### 失败方式

模型 alias、提示词、schema、评分门槛或查询策略变化后，结果改变但审计记录看不出原因。

### 防护

- 所有语义结果保存实际模型名、prompt/schema version；所有规则保存 policy version。
- alias 可用于开发，生产评测后优先固定可用 snapshot。
- 变更 policy/prompt 前运行冻结 fixture，对漏斗和 Reviewer 结论做 diff。
- 不把旧结果自动重算；显式 migration/re-evaluation run。

## P2：人类审核变成橡皮图章

### 失败方式

Draft PR 数量过多、正文缺乏证据、差异不稳定或 Reviewer 理由模糊，最终人类只看绿色检查就 merge。

### 防护

- 保持每日预算和严格前置门槛，宁少勿滥。
- PR 模板直接展示来源 SHA、许可证、工作流摘要、证据、风险和 Reviewer 不确定性。
- 将机器生成文件集中、排序稳定，diff 可预测。
- 统计人类拒绝原因和修改量，反向调整过滤/评分，不自动绕过。

## 风险验证清单

在允许真实 Publisher 运行前，必须有证据证明：

- [ ] 恶意 README 无法触发工具或读取秘密。
- [ ] 候选仓库的任何文件都不会被执行、import 或安装。
- [ ] GitHub App 无法 push 默认分支、merge 或修改 ruleset。
- [ ] `NOASSERTION`、多许可证和许可证冲突均被拒绝。
- [ ] Reader 对超大目录/文件按预算停止，并给出 stop reason。
- [ ] 相同 SHA 重跑不会重复生成 Draft PR。
- [ ] PR 成功而状态 checkpoint 失败时可以从远端恢复。
- [ ] Validator error 无法被 Reviewer YES 覆盖。
- [ ] state branch 丢失时，SQLite 可由 JSON 清单重建。
- [ ] 日志、state、artifact、Skill 和 PR 均通过 secret scan。

