# PatientCare-Agent 后续重构计划 V3

生成日期：2026-04-25

## 1. 目标

V2 已经完成了 Adaptive Evidence Routing、结构化工具直达、Evidence Cache、Agent Ops 指标和前端中文化展示。本计划聚焦 V2 之后仍会影响真实演示、准生产可信度和后续维护成本的问题。

这份文档不只做复盘，而是把可优化点拆成可以直接执行的工程任务。每个任务都包含当前问题、目标状态、建议改法和验收标准，方便后续按优先级逐项落地。

## 2. 当前亮点

### 2.1 Adaptive Evidence Routing 已经具备产品雏形

当前 `/api/agent/query` 不再只有完整 agent loop，而是会根据意图、风险和缓存状态选择不同路线：

- `template`：闲聊、越界问题等轻量回复。
- `risk_guard`：高风险场景优先安全兜底。
- `semantic_cache`：命中近期证据缓存时直接返回。
- `tool_direct`：明确患者查询直接调用结构化工具。
- `agent_loop`：复杂或低置信场景回退到完整 Agent。

这让项目从“LLM 聊天 Demo”更接近“医疗随访工作台中的智能证据路由层”。

### 2.2 工具调用与证据返回更结构化

后端已经开始返回 `route_type`、`route_reason`、`intent_confidence`、`cache_hit`、`evidence`、`tool_outputs` 和 `runtime_metrics`。前端也将这些字段翻译成中文标签，便于解释“为什么系统这么回答”。

### 2.3 Agent Ops 指标开始沉淀

`AgentRunMetric` 会记录单次请求的执行路径、耗时、工具调用数量、风险等级、缓存命中、回退原因等信息。`agent_metrics_service` 会聚合成功率、p50/p95 延迟、Adaptive Route 命中率、Evidence Cache 命中率、隐私阻断率等指标。

这为后续做 benchmark、稳定性评估和简历亮点提供了基础。

### 2.4 前端体验已经从“拼 prompt”转向“结构化请求”

前端工作台现在发送原始 `query`、`patient_code`、`actor_role` 和 `access_purpose`，不再把长上下文直接拼进用户问题。这个方向是正确的：前端负责交互，后端负责权限、上下文、证据和安全路由。

## 3. 必须优先修复的问题

### P1-1. 医护权限不能继续由客户端声明

**当前问题**

`app/schemas/agent.py` 中的 `actor_role` 和 `access_purpose` 来自请求体默认值，后端主要检查字符串是否等于 `clinician` 和 `follow_up_care`。这对本地 demo 可以成立，但如果用于对外演示或准生产说明，会被质疑为“客户端自证权限”。

**真实风险**

攻击者或错误前端都可以伪造请求体，声明自己是 clinician。医疗场景里，权限来源必须来自服务端可信上下文，而不是用户输入。

**目标状态**

前端只传 `query` 和 `patient_code`。`actor_role`、`access_purpose`、`operator_id`、`tenant_id` 等访问上下文由后端从登录态、测试会话或受控 demo header 注入。

**建议改法**

1. 新增服务端上下文模型，例如 `AgentAccessContext`：
   - `actor_role`
   - `access_purpose`
   - `operator_id`
   - `tenant_id`
   - `is_demo_context`
2. 在 FastAPI dependency 中解析访问上下文：
   - 正式模式：从认证中间件或 session 获取。
   - demo 模式：允许从受控 header 或配置注入，但不要从普通请求体读取。
3. `AgentQueryRequest` 保留 `patient_code`，逐步废弃请求体里的 `actor_role` 和 `access_purpose`。
4. 在路由中统一使用 dependency 注入的上下文。
5. Agent Ops 指标继续记录 `actor_role` 和 `access_purpose`，但来源改为服务端上下文。

**建议涉及文件**

- `app/schemas/agent.py`
- `app/api/routes/agent.py`
- `app/db/models.py`
- `frontend/src/pages/workspace/WorkspacePage.tsx`

**验收标准**

- 前端请求体不再包含 `actor_role` 和 `access_purpose`。
- 直接伪造请求体权限字段不会影响后端实际访问上下文。
- 未携带合法服务端上下文时，患者证据类查询返回 401 或 403。
- 原有工作台 demo 在配置了 demo context 后仍可运行。

**建议测试**

- 增加 API 测试：无上下文、非法上下文、合法 clinician follow-up 上下文。
- 增加回归测试：`patient_code` 正常传入时仍能查到患者证据。

### P1-2. 工具输出和缓存不能暴露完整敏感患者字段

**当前问题**

`app/services/mcp_tool_service.py` 中 `serialize_patient` 会返回 `phone`、`id_number`、`address`、`emergency_contact_name`、`emergency_contact_phone` 等完整敏感字段。Agent 响应里的 `tool_outputs`、`evidence` 和 Evidence Cache 都可能保存或展示这些字段。

**真实风险**

即使最终自然语言回答做了克制，结构化 `tool_outputs` 仍可能在前端调试区、浏览器缓存、日志、接口响应或测试快照中泄露敏感信息。

**目标状态**

默认所有 Agent 响应、Evidence Cache 和前端展示只使用 safe serializer。完整字段只允许在明确 debug 模式、受控环境和服务端权限检查通过后返回。

**建议改法**

1. 新增患者安全序列化函数，例如 `serialize_patient_safe`：
   - 保留：`patient_code`、`full_name`、`gender`、年龄或出生年份、必要临床摘要。
   - 脱敏：手机号显示后四位，身份证只显示后四位。
   - 默认移除：详细地址、完整紧急联系人电话、内部数据库 id。
2. 将给 Agent、Evidence Cache 和前端的工具结果切换到 safe serializer。
3. 保留完整 serializer，但只用于服务端内部逻辑或显式 debug。
4. 给 `tool_outputs` 增加输出策略：
   - `safe`：默认。
   - `debug_redacted`：展示字段名但值脱敏。
   - `internal_full`：仅服务端内部，不返回前端。
5. 检查日志、缓存、测试快照，不保存完整身份证和手机号。

**建议涉及文件**

- `app/services/mcp_tool_service.py`
- `app/services/evidence_cache_service.py`
- `app/api/routes/agent.py`
- `frontend/src/components/chat/MessageList.tsx`

**验收标准**

- 普通 `/api/agent/query` 响应中不出现完整手机号、身份证号和紧急联系人电话。
- Evidence Cache 中不保存完整敏感字段。
- 前端证据区和工具输出区不会显示完整敏感字段。
- Debug 模式即使返回更多字段，也必须明确脱敏或仅在受控配置开启。

**建议测试**

- 增加敏感字段泄露测试：断言响应 JSON 不包含完整 `phone`、`id_number`。
- 增加缓存测试：断言缓存 evidence 不包含完整敏感字段。
- 增加前端快照或组件测试：确认工具输出展示的是脱敏摘要。

## 4. 近期应完成的优化

### P2-1. 用 embedding/FAISS 替换 SequenceMatcher 作为 Evidence Cache 命中逻辑

**当前问题**

`app/services/evidence_cache_service.py` 的 `query_similarity` 使用 `SequenceMatcher` 和字符 bigram 近似匹配。它可以处理“最近一次随访计划”和“随访计划是什么”这类相近表达，但本质仍是字符串相似度，不是真正的语义匹配。

**为什么要改**

医疗随访问题常有同义表达，例如：

- “她下次什么时候复查”
- “最近安排的随访是哪天”
- “这个患者后续还要去哪个科”

这些问题字面差异较大，但语义可能指向同一类证据。字符串相似度容易漏命中，也容易被相似字面误导。

**目标状态**

Evidence Cache 使用 embedding 向量进行 prototype matching。每条缓存保存查询 embedding，查询时用向量相似度检索候选，再结合患者、权限、意图、source_version 和 TTL 做最终判断。

**建议改法**

1. 复用或抽象现有 embedding 能力，优先检查 `app/services/memory_vector_service.py` 是否已有可复用接口。
2. 为 Evidence Cache 新增 embedding 字段或旁路索引：
   - SQLite demo：embedding JSON 列或单独表。
   - 准生产：FAISS index 加 SQLite metadata。
3. 查询流程调整为：
   - 根据 `patient_id`、`actor_role`、`access_purpose`、`intent` 过滤候选 metadata。
   - 用 query embedding 在 FAISS 中召回 top-k。
   - 校验 `source_version`、`expires_at` 和相似度阈值。
   - 命中后更新 `hit_count` 和 `last_hit_at`。
4. 保留 `SequenceMatcher` 作为 fallback，用于 embedding 服务不可用时降级。
5. Agent Ops 增加或明确记录：
   - `cache_match_strategy`: `embedding` / `string_fallback`
   - `cache_similarity_score`
   - `fallback_reason`

**建议涉及文件**

- `app/services/evidence_cache_service.py`
- `app/services/memory_vector_service.py`
- `app/db/models.py`
- `tests/test_agent_harness.py`
- `tests/test_agent_metrics.py`

**验收标准**

- 同义问题可以命中同一条有效缓存。
- 不同意图、不同患者、不同访问目的之间不会串缓存。
- 数据源变化后仍会因为 `source_version` 不一致而失效。
- embedding 服务不可用时系统降级到字符串 fallback，并记录原因。

**建议测试**

- 同义表达命中测试。
- 跨患者隔离测试。
- source_version 变化失效测试。
- embedding 不可用 fallback 测试。

### P2-2. 数据库演进改为正规 migration

**当前问题**

`app/db/init_db.py` 当前使用 `Base.metadata.create_all` 加 `PRAGMA table_info` 和 `ALTER TABLE` 处理 schema 演进。这个方式适合本地 demo，但字段越来越多后会难以回滚、难以审计，也容易遗漏索引和约束。

**目标状态**

引入 Alembic 或建立显式 migration 脚本，让 schema 变更可追踪、可回滚、可重复执行。

**建议改法**

1. 如果项目目标是准生产，优先引入 Alembic：
   - 初始化 `alembic.ini` 和 `migrations/`。
   - 将当前模型状态作为 baseline migration。
   - 后续新增字段、索引、表全部走 revision。
2. 如果暂时保持轻量 demo，可建立 `app/db/migrations/`：
   - 每个脚本有版本号、说明和幂等检查。
   - `init_db` 只负责建库和执行待执行 migrations。
3. 将当前散落在 `_ensure_sqlite_columns` 的 ALTER 逻辑迁入 migration。
4. 为 `SemanticEvidenceCache`、`AgentRunMetric` 常用查询字段补索引。

**建议涉及文件**

- `app/db/init_db.py`
- `app/db/models.py`
- 新增 `migrations/` 或 `app/db/migrations/`

**验收标准**

- 新库可以从空库初始化到最新 schema。
- 旧库可以迁移到最新 schema。
- migration 可以重复执行，不会因字段已存在失败。
- schema 变更有版本记录和说明。

**建议测试**

- 空 SQLite 数据库初始化测试。
- 旧 schema fixture 迁移测试。
- 重复运行 migration 测试。

### P2-3. 将 Agent 路由逻辑从单一路由文件拆出服务层

**当前问题**

`app/api/routes/agent.py` 承载了请求解析、患者解析、意图识别、路由选择、工具调用、缓存读写、Agent loop、指标记录和响应组装。随着 V2 能力增加，这个文件会继续膨胀，后续修 bug 和写单测都会变慢。

**目标状态**

API route 只负责 HTTP 输入输出，核心决策逻辑进入服务层。这样可以对路由策略、缓存策略和指标记录做独立单元测试。

**建议改法**

1. 新增 `AgentOrchestrator` 或 `AgentQueryService`：
   - 输入：query、patient_code、access_context、debug flags。
   - 输出：`AgentQueryResponse` 需要的结构化结果。
2. 新增 `EvidenceRoutingService`：
   - 负责选择 `template`、`risk_guard`、`semantic_cache`、`tool_direct`、`agent_loop`。
3. 新增 `AgentMetricsRecorder`：
   - 负责将执行结果转为 `AgentRunMetric`。
4. Route 层只保留 dependency、异常映射和 response model。

**建议涉及文件**

- `app/api/routes/agent.py`
- 新增 `app/services/agent_query_service.py`
- 新增 `app/services/evidence_routing_service.py`

**验收标准**

- `agent.py` route 文件明显变薄，核心业务逻辑可在无 HTTP 环境下测试。
- 每种 `route_type` 都有服务层单元测试。
- 原有 API 响应结构保持兼容。

**建议测试**

- route smoke test。
- routing service 单元测试。
- metrics recorder 单元测试。

### P2-4. 量化指标需要和真实目标绑定

**当前问题**

Agent Ops 已经记录了很多指标，但部分命名仍保留历史包袱，例如 `fast_path_hit_rate` 和 `high_frequency_acceleration_rate`。此外，目前更多是运行时统计，还没有和“回答正确性、隐私安全、风险兜底、缓存收益”这些目标形成稳定 benchmark。

**目标状态**

指标分成四类，并和测试集绑定：

- 效率：p50/p95 延迟、平均节省耗时、Agent loop fallback rate。
- 安全：隐私字段泄露率、权限拒绝率、风险兜底触发率。
- 正确性：随访、用药、风险、病例摘要等固定问题集的答案通过率。
- 稳定性：缓存失效率、工具错误率、低置信意图率。

**建议改法**

1. 保留兼容字段，但前端和文档主推 `adaptive_route_hit_rate`。
2. 增加 benchmark fixture：
   - 高频随访查询。
   - 用药提醒查询。
   - 风险事件查询。
   - 越权访问查询。
   - 同义表达缓存查询。
3. 生成 benchmark report：
   - 请求数。
   - 正确路由率。
   - 平均耗时和 p95。
   - 隐私泄露检查结果。
   - 失败样例。
4. Resume 文档中只写已被 benchmark 支撑的指标，不写未验证的固定数字。

**建议涉及文件**

- `app/services/agent_metrics_service.py`
- `tests/test_agent_metrics.py`
- `tests/test_benchmark_report.py`
- `docs/resume_patientcare_agent_project.md`

**验收标准**

- Ops 面板和文档统一使用 Adaptive Evidence Routing 叙事。
- benchmark report 可以稳定生成。
- 每个关键指标都有定义和数据来源。
- 简历文档中的指标能追溯到测试或报告。

**建议测试**

- 指标聚合单元测试。
- benchmark report 生成测试。
- 固定测试集回归测试。

## 5. 中期可优化项

### P3-1. 前端增加真实浏览器冒烟测试

**当前问题**

目前主要验证是 `npm run build`，可以保证编译通过，但不能保证工作台真实交互、患者切换、消息展示和 Ops 卡片在浏览器中表现正确。

**目标状态**

使用 Playwright 或等价浏览器测试覆盖核心用户路径。

**建议场景**

- 打开工作台。
- 选择患者。
- 输入随访问题。
- 验证回答、路线标签、证据区和指标区正常展示。
- 切换患者后输入框和上下文不串。

**验收标准**

- 本地一条命令可以跑完浏览器 smoke test。
- 截图或断言能发现空白页、接口失败、关键标签缺失。

### P3-2. 文档与简历叙事统一

**当前问题**

部分旧文档仍使用 `fast path` 或“高频查询加速链路”作为核心表达。V2 之后更准确的表达应该是 Adaptive Evidence Routing，其中包含缓存、工具直达、风险兜底和 Agent loop fallback。

**目标状态**

所有对外材料统一为：

- Adaptive Evidence Routing
- Structured Tool Direct
- Evidence Cache
- Risk Guard
- Agent Ops Observability

**验收标准**

- 简历文档不夸大未完成能力。
- 对外描述和代码实现一致。
- 不把字符串相似度缓存称为真正 embedding semantic search，除非 P2-1 已完成。

### P3-3. 患者数据访问审计

**当前问题**

Agent Ops 记录的是运行指标，但医疗系统还需要回答“谁在什么目的下访问了哪个患者的哪些数据”。

**目标状态**

新增访问审计日志，独立于性能指标：

- operator_id
- patient_code
- access_purpose
- accessed_resource
- route_type
- timestamp
- decision: allowed / denied

**验收标准**

- 每次患者证据访问都有审计记录。
- 权限拒绝也会记录。
- 审计日志不保存完整敏感字段。

## 6. 推荐执行顺序

1. **先修敏感字段泄露**：这是最容易被真实评审指出的问题，也是医疗项目最重要的可信度基础。
2. **再修服务端权限上下文**：让“医护访问”从客户端声明变成后端可信注入。
3. **升级 Evidence Cache 到 embedding/FAISS**：把 semantic-like cache 变成真正可解释的语义缓存。
4. **正规化数据库 migration**：降低后续 schema 演进成本。
5. **拆分 Agent route 服务层**：为后续能力扩展和单元测试铺路。
6. **完善 benchmark 和浏览器 smoke test**：让指标、简历和演示都能被验证。
7. **统一文档叙事和审计能力**：增强对外表达和合规感。

## 7. Definition of Done

完成 V3 后，项目应达到以下状态：

- 普通响应、缓存、前端展示和日志中不暴露完整敏感身份字段。
- 医护权限来自服务端上下文，而不是请求体自声明。
- Evidence Cache 至少支持 embedding 检索，字符串相似度只作为 fallback。
- 数据库 schema 变更有 migration 记录。
- Agent 查询核心逻辑可以脱离 HTTP route 单测。
- Ops 指标可以解释效率、安全、正确性和稳定性。
- 前端核心工作流有浏览器级 smoke test。
- 对外文档、简历和项目介绍不夸大未实现能力。

## 8. 建议验收命令

后续每完成一个任务，建议至少运行：

```bash
pytest -q
npm run build
```

如果新增浏览器测试，再补充：

```bash
npm run test:e2e
```

如果引入 Alembic，再补充：

```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

## 9. 给后续实现者的注意事项

- 不要为了展示效果把权限字段继续放在前端请求体里。Demo 模式也应该通过服务端受控上下文注入。
- 不要让 `tool_outputs` 成为隐私绕过点。自然语言回答安全不代表结构化 JSON 安全。
- 不要把 `SequenceMatcher` 包装成 embedding 语义检索。可以称为 string fallback 或 semantic-like prototype，直到真正接入 embedding。
- 不要一次性重写整个 Agent。优先修 P1，再做 P2，最后做结构性清理。
- 每个优化都要配套测试，否则后续很难证明它解决了真实问题。
