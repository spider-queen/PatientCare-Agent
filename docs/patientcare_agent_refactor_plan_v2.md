# PatientCare-Agent V2 重构计划：医护端诊后随访 Agent Harness

## Summary

本轮重构目标：将项目从“可运行的患者问答 Demo”收敛为“医生/随访专员使用的诊后随访 Agent 工作台”，让业务逻辑更贴近真实使用场景，同时在简历上突出 Agent Harness 工程能力。

核心定位：

- 使用者：医生、护士、随访专员等医护人员。
- 场景：选择患者后，进行病历摘要、随访计划、用药提醒、复诊重点、风险识别和证据复核。
- Agent 价值：不是单次问答，而是在受控 harness 中完成意图识别、证据检索、工具调用、风险拦截、上下文管理和可观测记录。

本轮计划引入更适合简历表达的名称：

> Adaptive Evidence Routing，中文可表述为“自适应证据路由”。

它替代当前较朴素的 `fast path` 概念，强调系统会根据风险、权限、意图置信度、语义缓存命中和证据新鲜度，选择“模板回复、证据缓存、结构化工具直达或完整 Agent Tool Loop”。

## Key Changes

### 1. 医护端工作台产品逻辑

- 明确当前页面不是患者本人端，而是医生/随访专员工作台。
- 快捷问题不再默认填入聊天框；初次进入和切换患者时，输入框保持空白。
- 快捷问题使用患者姓名，而不是患者编号：
  - 推荐：“总结王建国最近一次心内科复诊重点”
  - 不推荐：“总结 P0003 最近一次心内科复诊重点”
- 若患者概览未加载成功，快捷问题使用“该患者”，避免暴露技术编号。
- 患者编号只作为结构化检索字段传给后端，不拼进自然语言 prompt。
- Agent 回答面向医护人员，不直接对患者说“您好”；使用“该患者”“患者王建国”“王建国先生”等医护工作语气。
- 页面文案统一中文为主；保留少量专业英文小标题即可，其余指标、按钮、状态、空态和元数据标签应中文化。

### 2. 上下文与权限边界

- 前端不再构造长 prompt，例如“当前患者编号”“处理要求”等应迁移到后端 harness 上下文。
- `AgentQueryRequest.query` 只保存医护人员原始自然语言问题。
- `patient_code`、`actor_role=clinician`、`access_purpose=follow_up_care` 作为结构化字段进入后端。
- 医护工作台采用“已登录医护演示权限 + 患者选择审计”的 demo 模型，不要求医生输入患者手机号或身份证完成患者本人验权。
- 私有患者工具访问必须满足：
  - 已选择患者；
  - 当前 actor 是医护端；
  - 访问目的属于诊后随访；
  - 工具调用写入审计和运行指标。
- `identity_verification` 保留为患者本人端预留字段，本轮不作为医护端常规访问路径。

### 3. 意图识别升级

当前意图识别主要依赖关键词规则，容易被面试官理解为简单 `if-else`。本轮升级为分层意图识别器：

1. Deterministic Guard
   - 优先识别高风险、闲聊、越界、图片请求。
   - 高风险问题不能被缓存或加速链路绕过。

2. Rule-based Router
   - 使用关键词和业务词典识别高频随访意图。
   - 覆盖最近就诊、病历摘要、随访计划、用药提醒、患者概览等场景。

3. Semantic Intent Matching
   - 为每类 intent 维护少量中文样例，例如“总结最近复诊重点”“看一下上次复查说了什么”。
   - 将用户问题与 intent 样例做 embedding 相似度匹配。
   - 输出 `intent`、`confidence`、`route_reason`、`use_adaptive_routing`。

4. LLM Classifier Fallback
   - 仅当规则和语义匹配低置信度时调用 LLM 做结构化分类。
   - 避免所有请求都依赖 LLM 分类，降低成本和延迟。

目标链路：

```text
用户问题
→ 风险/越界/闲聊 guard
→ 规则意图识别
→ 语义 intent matching
→ 低置信度 LLM classifier fallback
→ 得到稳定的 route decision
```

### 4. Adaptive Evidence Routing

将当前 `fast path` 重命名并升级为 `Adaptive Evidence Routing`，突出它不是简单跳过 LLM，而是一个分层执行路由器。

路由顺序：

```text
1. Risk Guard
2. Clinician Access Check
3. Intent Confidence Check
4. Semantic Evidence Cache Lookup
5. Structured Tool Direct Route
6. Full Planner + Tool Loop Fallback
```

命中路径：

- 小问候、功能说明：模板回复。
- 高风险随访问题：风险 guard 回复并记录风险事件。
- 明确高频问题且证据缓存命中：复用 tool-backed evidence。
- 明确高频问题但缓存未命中：直接调用结构化工具并写入 evidence cache。
- 复杂问题、低置信度问题、图片问题：进入完整 Planner + Tool Loop。

需要记录：

- route_type：`template`、`risk_guard`、`semantic_cache`、`tool_direct`、`agent_loop`。
- route_reason：命中原因。
- intent_confidence：意图置信度。
- cache_hit：是否命中语义证据缓存。
- latency_saved_ms：相对完整 Agent Loop 的延迟收益估算。
- fallback_reason：为什么进入完整 Agent Loop。

### 5. Semantic Evidence Cache

不要直接缓存最终回答，而是缓存“工具证据”。这比缓存回答更适合医疗随访场景。

缓存对象示例：

```json
{
  "patient_id": 3,
  "actor_role": "clinician",
  "intent": "latest_visit",
  "query_embedding": [0.01, 0.02],
  "normalized_query": "总结最近一次复诊重点",
  "tool_name": "get_patient_visit_records",
  "tool_arguments": {"limit": 1},
  "evidence": {
    "visit_id": 12,
    "department": "心内科",
    "visit_time": "2026-03-14T10:00:00",
    "summary": "..."
  },
  "source_version": "visit_records:12:updated_at",
  "created_at": "2026-04-25T10:00:00",
  "expires_at": "2026-04-25T10:10:00"
}
```

命中条件：

- 同一患者或同一患者上下文；
- 同一医护访问目的；
- intent 一致；
- query embedding 相似度超过阈值；
- 证据源未更新；
- 未命中高风险 guard；
- 缓存未过期。

失效条件：

- 患者新增或更新病历、就诊记录、随访计划、用药提醒；
- 证据源 `updated_at` 变化；
- 缓存超过 TTL；
- 问题涉及高风险、诊断判断、用药调整、图片分析；
- intent 置信度低于阈值。

面试表达重点：

> 系统没有缓存大模型回答，而是缓存带来源版本的 tool-backed evidence，并通过患者隔离、证据新鲜度、风险优先级和置信度阈值控制复用边界。

### 6. 前端展示优化

- 聊天元数据区域不直接显示后端枚举：
  - `health_general` → “健康咨询”
  - `latest_visit` → “最近就诊”
  - `medical_followup` → “诊后随访”
  - `urgent` → “紧急风险”
  - `get_patient_medical_cases` → “病历记录查询”
- “证据来源”显示结构化摘要，而不是裸 JSON。
- “工具调用明细”继续折叠展示完整 JSON，用于演示 harness 可观测性。
- Ops 看板中文化：
  - `P50 Latency` → “P50 响应耗时”
  - `HF Acceleration` → “自适应路由命中率”
  - `Tool Success` → “工具调用成功率”
  - `Privacy Blocks` → “隐私拦截率”
  - `Recent Runs` → “最近运行记录”
- 新增自适应路由指标：
  - 语义缓存命中率；
  - 证据缓存失效率；
  - 完整 Agent Loop fallback 比例；
  - 平均延迟节省；
  - 意图低置信度比例；
  - 风险 guard 拦截次数。

## Public Interfaces

### AgentQueryRequest

推荐新请求形态：

```json
{
  "query": "总结王建国最近一次心内科复诊重点",
  "patient_code": "P0003",
  "actor_role": "clinician",
  "access_purpose": "follow_up_care",
  "images": [],
  "debug_planner": false,
  "force_full_agent": false
}
```

字段说明：

- `query`：医护人员原始问题，不包含前端拼接上下文。
- `patient_code`：结构化患者选择字段。
- `actor_role`：本轮固定为 `clinician`。
- `access_purpose`：本轮固定为 `follow_up_care`。
- `identity_verification`：患者本人端预留，本轮医护端不发送。

### AgentQueryResponse

继续保留现有字段，并补充路由解释：

```json
{
  "answer": "...",
  "intent": "latest_visit",
  "intent_confidence": 0.91,
  "route_type": "semantic_cache",
  "route_reason": "matched latest_visit prototype and fresh evidence cache",
  "cache_hit": true,
  "evidence": [],
  "risk_level": null,
  "recommended_action": null,
  "runtime_metrics": {}
}
```

## Test Plan

### 前端测试

- 初次进入页面时输入框为空。
- 切换患者后输入框仍为空。
- 快捷问题显示患者姓名；患者信息未加载时显示“该患者”。
- 点击快捷问题后，输入框只包含自然语言问题，不包含患者编号。
- 提交请求时 `patient_code` 单独进入 payload。
- 页面主要文案中文化，截图中的中英文混杂问题得到修复。
- 证据来源和工具名经过中文映射展示。

### 后端测试

- `query` 不再包含前端拼接上下文。
- 医护端请求携带 `patient_code` 后可访问随访工具，并记录审计指标。
- 未选择患者时，私有工具访问被阻断。
- 高风险问题优先进入 risk guard，不进入缓存或工具直达链路。
- 规则意图识别、语义意图匹配、LLM fallback 均有覆盖测试。
- 语义 evidence cache 命中时返回 `route_type=semantic_cache`。
- 证据源更新后缓存失效并重新调用工具。
- 低置信度问题进入完整 Agent Tool Loop。

### 验证命令

```bash
conda --no-plugins run -n patient-agent-dev pytest -q
cd frontend && npm run build
```

## Resume Highlights

可写入简历的项目亮点：

- 设计医生/随访专员场景下的诊后随访 Agent Harness，支持患者上下文、记忆检索、工具调用、风险拦截和运行可观测。
- 实现 Adaptive Evidence Routing：结合规则 guard、语义意图匹配、证据缓存和完整 Tool Loop fallback，降低高频随访问题响应延迟。
- 构建 Semantic Evidence Cache：缓存结构化工具证据而非 LLM 回答，通过患者隔离、证据版本、TTL 和风险优先级控制医疗数据复用边界。
- 设计分层意图识别器：规则路由、embedding prototype matching、低置信度 LLM classifier fallback。
- 建立 Agent Ops 指标体系：路由命中率、缓存命中率、工具成功率、隐私拦截率、风险升级次数、fallback 原因和延迟收益。

## Assumptions

- 当前工作台定位为医护端，不做患者本人端。
- 本轮继续使用 SQLite、Qwen OpenAI-compatible API、现有 FAISS/embedding 能力。
- 不引入真实医院 SSO、RBAC 或短信 OTP，只实现 demo 级医护访问上下文和审计链路。
- 缓存优先使用 SQLite + embedding metadata；若现有 FAISS 结构复用成本低，可复用当前 memory vector service。
- 所有医疗回答仍定位为随访辅助，不替代医生诊断、处方或正式医疗决策。
