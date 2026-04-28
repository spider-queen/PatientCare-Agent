# PatientCare-Agent 诊后随访 Harness 重构计划

## Summary

目标：把项目从“可运行医疗 Agent Demo”升级为“面向诊后随访场景的 AI 后端简历项目”，重点突出 Agent Harness、Function Tools、分层记忆、隐私验权、业务安全边界和可观测性。

当前审查结论：

- 已有基础：`Planner -> Tool Loop -> Finalizer`、LLM function/tool calling、短期/长期记忆、fast path、运行指标、前端 Ops 看板。
- 主要短板：`agent.py` 编排过重；患者识别与身份验权边界混在一起；前端会把手机号/身份证号注入 prompt；随访业务对象不足；隐私访问缺少审计日志；医疗无关问题缺少明确边界；当前测试有 1 个编码门禁失败。
- 当前测试基线：`21 passed, 1 failed`，失败点是 `tests/test_agent_harness.py:550` 存在乱码测试字符串。

## Key Changes

### 重构 Agent 主链路

- 将 `app/api/routes/agent.py` 中的患者解析、记忆构造、fast path、指标记录、持久化逻辑拆到 service 层。
- 保留 `POST /api/agent/query` 主入口，路由只负责参数接收、依赖注入和返回响应。
- 将 Agent 上下文结构固定为：用户目标、领域意图、患者上下文、身份状态、记忆上下文、执行计划、工具证据、风险提示。

### 明确工具层命名与边界

- 将“核心工具层”统一表述为 `Function Tools / Tool Calling`，不再把主链路称为完整 MCP 集成。
- 保留 `app/mcp_server.py` 作为可选 MCP Server 适配入口，但简历和文档中说明主链路基于 OpenAI-compatible function calling。
- 新增工具时按 function tool 规范设计：清晰 schema、结构化返回、失败原因、隐私风险等级。

### 增加领域边界与有限闲聊

- 在进入 Planner 前增加 intent guard：`medical_followup`、`patient_record_query`、`health_general`、`smalltalk`、`out_of_domain`。
- `smalltalk` 只支持问候、感谢、功能说明和使用引导，走轻量模板，不进入完整 Agent 工具链。
- `out_of_domain` 礼貌说明能力边界，引导用户回到患者服务、诊后随访、病历查询、用药提醒或健康咨询场景。
- 医疗相关但高风险的问题进入风险识别，不直接给诊断、处方或停药建议。

### 修正身份验权边界

- 不再用数据库中的手机号/身份证号自动生成 bootstrap 验权结果。
- `AgentQueryRequest` 增加可选字段：`patient_code`、`identity_verification`，其中 `identity_verification` 可包含用户主动输入的 `phone` 或 `id_number`。
- 前端不再把完整手机号/身份证号拼进 prompt；患者概览默认展示脱敏字段。
- 所有私有数据工具继续由 `AgentRunState.private_access_required()` gate 控制，未验权时只返回阻断结果。

### 新增诊后随访业务模型

- 增加 `FollowUpPlan`：随访目标、来源就诊、科室、医生、计划时间、状态、注意事项。
- 增加 `MedicationReminder`：药品名、剂量、频次、起止时间、注意事项、来源病历/就诊。
- 增加 `RiskEvent`：本轮问答命中的风险级别、风险类别、触发词、建议动作、关联 `run_id`。
- 使用轻量幂等迁移函数扩展 SQLite schema，不引入 Alembic。

### 扩展 Function Tools

- 新增 `get_follow_up_plans`、`get_medication_reminders`、`assess_follow_up_risk`。
- 工具返回统一结构：`found`、`count`、`records`、`evidence`、`error`。
- `assess_follow_up_risk` 先做规则识别，命中胸痛、呼吸困难、严重过敏、停药/改药等高风险场景时返回升级建议，Finalizer 必须保守回答。

### 增强输出与前端展示

- `AgentQueryResponse` 增加可选 `intent`、`evidence`、`risk_level`、`recommended_action`、`runtime_metrics`。
- 前端聊天消息展示证据来源、风险等级、工具调用摘要。
- Ops 卡片补充隐私阻断率、风险升级次数、smalltalk/out-of-domain 占比、fast path 与完整 Agent 对比指标。

## Test Plan

- 先修复编码门禁：替换 `tests/test_agent_harness.py:550` 的乱码 query，并确认 `test_text_encoding.py` 通过。
- 后端单元测试：
  - `smalltalk` 走模板回复，不调用 LLM tool loop。
  - `out_of_domain` 礼貌拒答并记录 intent。
  - 未提供 `identity_verification` 时，私有工具必须被阻断。
  - 提供正确手机号/身份证号时，私有工具可访问。
  - fast path 只有在显式验权成功后才可执行。
  - 新增随访计划、用药提醒、风险识别工具的正常、空结果、错误结果场景。
  - 轻量迁移函数可重复执行且不破坏旧库。
- API 回归测试：
  - `POST /api/agent/query` 旧请求仍可返回答案。
  - 新字段 `intent`、`evidence`、`risk_level`、`recommended_action` 在相关场景出现。
  - 私有数据访问写入审计/指标。
- 前端验证：
  - `npm run build` 通过。
  - 工作台不再把完整 PII 拼进 prompt。
  - 聊天区能展示风险提示、证据来源和领域边界提示。
- 全量验证命令：
  - `conda --no-plugins run -n patient-agent-dev pytest -q`
  - `cd frontend && npm run build`

## Assumptions

- 本轮按“中等重构”执行：保留现有主 API，不做大规模框架替换。
- 项目主场景固定为“诊后随访”，暂不完整展开导诊、支付、处方、正式诊断等生产医疗能力。
- 工具层对外表述为 `Function Tools / Tool Calling`；`MCP Server` 仅作为可选适配入口，不作为主链路卖点。
- 用户医疗无关问题采用“有限闲聊”策略：允许问候和功能咨询，拒绝通用知识任务。
- SQLite 继续作为演示数据库；schema 演进采用幂等初始化/迁移函数。
- 不接入真实短信 OTP、医院 SSO 或外部审计平台，只实现可解释的 demo 级身份凭证和审计链路。
- 医疗回答始终定位为患者服务辅助，不替代医生诊断、处方或用药调整。
