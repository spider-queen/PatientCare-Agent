# PatientCare Agent

一个面向患者服务场景的全栈智能助手项目。

该项目将 FastAPI 后端、React 工作台前端、基于 Qwen 的智能问答、患者数据管理、多模态输入，以及短期 / 长期记忆检索整合到一个可运行的示例系统中。

在当前版本中，项目进一步补充了 Agent 执行治理、医护随访访问上下文、风险前置分流、高频查询加速、语义证据缓存和运行指标看板等能力，用于增强医疗随访问答链路的可控性、可观测性和可复盘性。

当前版本更偏向本地演示和项目展示用途，尚未达到生产环境可直接部署的医疗系统标准。所有医疗相关回答都应由专业医护人员复核。

## 项目简介

PatientCare Agent 主要面向以下医疗服务场景：

- 患者身份核验
- 患者档案、病例和就诊记录查询
- 支持图片输入的多模态问答
- 短期对话记忆管理
- 长期记忆提取与检索
- 面向患者服务流程的 Web 工作台
- 医护随访场景下的随访计划、用药提醒和风险信号辅助处理

## 本次优化重点

相比旧版 README 描述的基础全栈助手，本版本重点新增或强化了以下模块：

- **访问控制与脱敏**：敏感患者记录查询需要医护随访访问上下文或患者身份核验，工具输出会对手机号、证件号等敏感字段做脱敏处理。
- **高频查询加速**：对“最近一次就诊”“患者基本信息”“病历摘要”“随访计划”“用药提醒”等标准化问题，优先走结构化工具直达或语义证据缓存。
- **随访风险识别**：对胸痛、呼吸困难、自行停药、严重过敏等高风险信号做前置分流，并记录风险事件。
- **运行指标看板**：新增 Agent 运行指标表和 `/api/dashboard/agent-ops` 接口，支持展示 p50/p95 延迟、加速命中率、工具成功率、身份核验覆盖率等指标。
- **Benchmark 评估**：新增固定 benchmark 脚本和报告输出，用于对比高频查询加速链路与完整 Agent Loop 的耗时差异。

## 核心能力

- 基于 Qwen / DashScope 的智能问答入口：`POST /api/agent/query`
- 患者资料、病例、就诊记录、随访计划、用药提醒等结构化查询
- 图片输入的多模态问答
- 患者身份核验、医护随访访问上下文校验和敏感字段脱敏
- 短期会话记忆自动写回
- 长期偏好、用户画像、关键事件抽取与混合检索
- 高频查询自适应路由与语义证据缓存
- 高风险随访信号前置识别与风险事件记录
- Agent 运行指标采集、聚合、benchmark 和前端 Ops 看板

## 技术栈

### 后端

- Python 3.12
- FastAPI
- SQLAlchemy
- Pydantic v2
- SQLite
- FAISS
- MCP Python SDK
- OpenAI 兼容 SDK 调用 Qwen / DashScope

### 前端

- React 18
- Vite
- TypeScript
- Tailwind CSS
- TanStack Query
- Zustand

## 架构说明

项目按职责拆分为五层：

1. **API 接入层**
   - 使用 FastAPI 暴露 Agent、Dashboard、Patients、Medical Cases、Visit Records 和 Memory 等接口。
   - `app.main` 统一挂载 `/api`、`/media`，并在 `frontend/dist` 存在时托管前端构建产物。

2. **Agent 编排层**
   - 由 `QwenMCPAgent` 组织 Planner、多候选计划合并、工具调用、记忆上下文注入、多模态输入处理和 Finalizer 汇总。
   - `POST /api/agent/query` 负责患者预识别、访问上下文检查、风险分流、路由决策、执行指标记录和记忆回写。

3. **Tool / MCP 风格能力层**
   - 将内部业务能力封装为可审计工具，包括身份验证、患者资料、病历、就诊记录、随访计划、用药提醒和随访风险评估。
   - 工具输出会被脱敏并转为结构化证据，供 Finalizer 生成最终答复。

4. **数据、记忆与缓存层**
   - 使用 SQLite 存储患者、病例、就诊记录、随访计划、用药提醒、风险事件、短期会话、长期画像、关键事件、语义证据缓存和 Agent 运行指标。
   - 使用 FAISS 支持长期关键事件向量检索；当向量能力不可用时，降级到关键词或最近事件召回。

5. **前端工作台层**
   - 使用 React 构建医护随访工作台，展示患者概览、聊天会话、最近就诊、长期记忆、关键事件和 Agent Ops 指标。

## 执行链路

`POST /api/agent/query` 的核心流程如下：

1. 解析请求，识别意图、图片输入和患者编号。
2. 对高风险随访信号执行 `risk_guard` 前置分流。
3. 对敏感患者记录查询检查医护随访访问上下文。
4. 预解析患者，构造短期记忆、长期画像和关键事件上下文。
5. 对高频标准化问题尝试结构化工具直达或语义证据缓存。
6. 无法加速时进入完整 `Planner - Tool Loop - Finalizer`。
7. 写回本轮短期记忆，并按 5 轮阈值触发长期记忆刷新任务。
8. 记录请求级运行指标，返回 `run_id`、证据、路由、风险和 runtime metrics。

## 项目结构

```text
.
|-- app/                    # FastAPI 应用、路由、服务、数据库、LLM 集成
|   |-- api/routes/         # Agent、Dashboard、Memory、Patients 等 API 路由
|   |-- db/                 # SQLAlchemy 模型、数据库会话、初始化逻辑
|   |-- llm/                # Qwen 客户端、Agent 编排、意图识别、领域技能
|   |-- schemas/            # Pydantic 数据模型
|   |-- services/           # 业务服务、记忆、缓存、指标和工具函数
|-- data/                   # 本地 SQLite 数据、上传媒体、FAISS 索引文件
|-- docs/                   # PRD、架构说明、可观测性方案和项目复盘文档
|-- frontend/               # React + Vite 前端工程
|   |-- src/
|   |-- package.json
|-- reports/                # Benchmark 输出报告
|-- scripts/                # 演示数据、本地测试和 benchmark 脚本
|-- tests/                  # 后端回归测试
|-- .env.example            # 环境变量模板
|-- README.md
|-- requirements.txt
```

## 主要接口

### Agent

- `POST /api/agent/query`
- `GET /api/health`

`/api/agent/query` 支持的关键字段：

- `query`：用户问题
- `patient_code`：可选，患者编号，例如 `P1001`
- `identity_verification`：可选，手机号或证件号核验信息
- `images`：可选，`image_url` 或 `image_base64`
- `debug_planner`：是否返回 Planner / 执行轨迹调试信息
- `force_full_agent`：是否强制绕过高频查询加速链路

敏感患者记录查询建议在请求头中传入演示访问上下文：

```http
X-Agent-Demo-Context: true
X-Agent-Actor-Role: clinician
X-Agent-Access-Purpose: follow_up_care
X-Agent-Operator-Id: demo-operator
X-Agent-Tenant-Id: demo-tenant
```

### Dashboard

- `GET /api/dashboard/patient-overview`
- `GET /api/dashboard/agent-ops`

### Memory

- `GET /api/memory/preferences`
- `PUT /api/memory/preferences`
- `POST /api/memory/conversations`
- `GET /api/memory/conversations`
- `POST /api/memory/extract/business`
- `POST /api/memory/extract/conversation`
- `GET /api/memory/events`
- `POST /api/memory/search/events`
- `GET /api/memory/profile`

### 患者数据

- `POST /api/patients`
- `GET /api/patients`
- `GET /api/patients/{patient_id}`
- `PUT /api/patients/{patient_id}`
- `POST /api/medical-cases`
- `GET /api/medical-cases`
- `GET /api/medical-cases/{case_id}`
- `PUT /api/medical-cases/{case_id}`
- `POST /api/visit-records`
- `GET /api/visit-records`
- `GET /api/visit-records/{visit_record_id}`
- `PUT /api/visit-records/{visit_record_id}`

## 快速开始

除特别说明外，以下命令均在仓库根目录 `PatientCare-Agent/` 下执行。

### 1. 创建 Python 环境

推荐使用 `conda`：

```bash
conda --no-plugins create --solver=classic -n patient-agent-dev python=3.12 -y
conda activate patient-agent-dev
```

### 2. 安装后端依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

然后编辑 `.env`：

```env
QWEN_API_KEY="your_qwen_api_key"
QWEN_MODEL="qwen3.5-plus"
QWEN_EMBEDDING_MODEL="text-embedding-v4"
QWEN_EMBEDDING_DIMENSIONS="1024"
```

可选配置：

- `QWEN_BASE_URL`：如果需要覆盖默认 DashScope 兼容接口地址，可以额外配置该变量。
- `EVIDENCE_CACHE_EMBEDDING_PROVIDER`：语义证据缓存的 embedding 来源，默认使用本地轻量特征；可配置为 `qwen` 使用 Qwen embedding，也可配置为 `off` 关闭。

### 4. 初始化或导入演示数据

项目默认使用本地 SQLite 数据库：

```text
data/patient_agent.db
```

如需导入演示数据，可执行：

```bash
sqlite3 data/patient_agent.db < scripts/seed_demo_data.sql
```

如果本机没有安装 `sqlite3`，也可以使用任意 SQLite 可视化工具导入该 SQL 文件。

### 5. 启动后端服务

```bash
python -m uvicorn app.main:app --reload
```

启动后可访问：

- API 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 健康检查：[http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

### 6. 启动前端服务

打开另一个终端窗口：

```bash
cd frontend
npm install
npm run dev
```

前端地址：

- 工作台：[http://127.0.0.1:5173](http://127.0.0.1:5173)

开发环境下，Vite 会将 `/api` 和 `/media` 请求代理到 `http://127.0.0.1:8000`。

## 本地构建预览

如果希望由 FastAPI 直接托管前端构建产物，可以先执行：

```bash
cd frontend
npm run build
cd ..
python -m uvicorn app.main:app --reload
```

然后访问：

- [http://127.0.0.1:8000](http://127.0.0.1:8000)

当 `frontend/dist` 存在时，`app.main` 会自动优先托管前端构建后的静态资源。

## 测试与 Benchmark

运行核心后端测试：

```bash
pytest tests/test_agent_harness.py tests/test_agent_metrics.py tests/test_benchmark_report.py tests/test_memory_search.py -q
```

运行固定 benchmark：

```bash
python scripts/benchmark_agent.py --case-set high_frequency --compare-modes
```

脚本会在 `reports/` 目录下生成 JSON 和 Markdown 报告，用于对比自适应路由与完整 Agent Loop 的延迟差异。

当前仓库内的示例报告 `reports/agent_benchmark_high_frequency_compare_20260424_221451.md` 记录了以下结果：

- 高频查询加速命中率：`60.0%`
- 加速链路平均耗时：`69 ms`
- 强制完整 Agent 平均耗时：`84004 ms`
- 对可加速样例的延迟下降：`99.9%`

> benchmark 结果与本机硬件、网络、模型服务响应和样例集有关，建议在展示前重新运行一次并引用最新报告。

## 本地脚本调试

项目中提供了一个简单脚本，用于直接测试 Agent：

```bash
python scripts/test_qwen_agent.py "请总结患者 P1001 最近一次就诊记录"
```

如果需要结合图片进行测试：

```bash
python scripts/test_qwen_agent.py "请分析这张图片中的检查信息" --image-file data/example.png
```

## 说明与边界

- 本项目没有实现完整登录系统、RBAC 或生产级医疗权限体系；当前安全治理聚焦于 Agent 工具调用前的访问上下文校验、患者身份核验和敏感字段脱敏。
- 高风险随访信号采用规则分流，目标是让这类问题绕过普通问答链路并返回保守安全建议，而不是提供诊断结论。
- 当前语义证据缓存用于本地演示和性能对比，生产环境需要更严格的租户隔离、审计、失效策略和安全评估。

## 许可证

本项目采用 MIT License。
