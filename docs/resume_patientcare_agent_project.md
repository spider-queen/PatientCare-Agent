# PatientCare-Agent 简历项目描述

## 推荐项目名称

`PatientCare-Agent：面向医疗随访场景的可观测智能问答系统`

## 三条简历版描述

- 设计并实现面向医疗随访场景的 `PatientCare-Agent`，基于 `FastAPI + React + Qwen + SQLite/FAISS` 打通患者信息、病历、就诊记录、短期会话与长期记忆链路，支持多轮问答、多模态输入、隐私验权和证据化回复。
- 将 Agent 主链路拆分为 `Planner-Tool Loop-Finalizer` 三阶段，封装 `4` 个 MCP 风格工具完成身份校验、患者资料、病历和就诊记录查询；引入显式执行状态管理与高频查询加速链路，对“最近一次就诊、患者基本信息、病历摘要”等标准化问题进行轻量化处理，减少冗余 LLM 调用和记忆检索开销。
- 构建 Agent 运行可观测性与评估体系，按请求记录 `run_id`、分阶段耗时、`p50/p95` 延迟、高频查询加速命中率、工具成功率、验权覆盖率、memory fallback 比例等指标，并提供 Ops 看板与固定 benchmark 脚本支撑效果评估和持续优化。

## 如果简历空间只能写两条

- 独立设计医疗随访 Agent 系统，基于 `FastAPI + React + Qwen + SQLite/FAISS` 实现患者问答、病历/就诊查询、多轮记忆增强和隐私验权闭环，支持工具调用与证据化回复。
- 引入显式执行状态、MCP 风格工具、高频查询加速链路和运行可观测性，支持统计 `p50/p95` 延迟、工具成功率、验权覆盖率、高频查询加速命中率等指标，并通过回归测试与 benchmark 脚本验证核心链路稳定性。

## 面试讲解重点

- 不是简单调用大模型 API，而是把 Agent 做成可控的业务执行链路：先规划，再验权和调用工具，最后基于证据收敛回答。
- 医疗场景下把隐私保护作为硬约束：涉及患者资料、病历和就诊记录时必须先完成身份校验，验权失败不返回敏感信息。
- 对高频标准化问题使用轻量化执行链路，避免所有请求都走完整 Agent 编排，降低简单查询的响应延迟和调用成本。
- 记忆系统分为短期会话记忆和长期事件/用户画像，并支持向量检索失败时回退到关键词或最近事件，提升系统可恢复性。
- 增加运行指标落库、Ops 看板和 benchmark 脚本，让项目从“能跑 demo”升级为“能评估、能调优、能运营”的 Agent 服务。

## 可量化指标口径

当前项目已经支持采集和展示以下指标，建议跑完固定 benchmark 后再把真实数值写入简历：

- `p50/p95` 请求延迟
- 高频查询加速命中率
- 加速链路平均耗时与完整 Agent 编排平均耗时差值
- 工具调用成功率
- 身份验权覆盖率
- memory fallback 比例
- memory refresh 触发率
- 分阶段耗时：患者解析、memory 构建、Agent 执行、结果持久化

## Benchmark 运行方式

先启动后端：

```bash
conda --no-plugins run -n patient-care-dev python -m uvicorn app.main:app --reload
```

再运行固定评测：

```bash
conda --no-plugins run -n patient-care-dev python scripts/benchmark_agent.py --repeat 3
```

脚本会在 `reports/` 目录下生成 JSON 和 Markdown 报告。拿到报告后，可以把简历里的泛化表述升级为：

- 针对高频标准化查询设计轻量化执行链路，高频查询加速命中率达到 `X%`，加速链路平均耗时较完整 Agent 编排降低 `Y ms / Z%`。
- 构建 Agent 运行评估体系，固定 benchmark 下 `p95` 延迟为 `X ms`，工具调用成功率达到 `Y%`，memory fallback 比例为 `Z%`。

## 不建议写法

- 不建议直接写 `fast path`，建议写“高频查询加速链路”或“意图识别驱动的轻量化执行链路”。
- 不建议在没有真实 benchmark 前写“提升 XX%”，可以先写“支持统计/评估”，跑出数据后再补百分比。
- 不建议只写 ReAct、RAG、LangChain 等概念词，应该落到业务约束、工具调用、记忆分层、验权前置、可观测性和评估指标。
