# PatientCare Agent

一个面向患者服务场景的全栈智能助手项目。

该项目将 FastAPI 后端、React 工作台前端、基于 Qwen 的智能问答、患者数据管理、多模态输入，以及短期 / 长期记忆检索整合到一个可运行的示例系统中。

## 项目简介

PatientCare Agent 主要面向以下医疗服务场景：

- 患者身份核验
- 患者档案、病例和就诊记录查询
- 支持图片输入的多模态问答
- 短期对话记忆管理
- 长期记忆提取与检索
- 面向患者服务流程的 Web 工作台

当前版本更偏向本地演示和项目展示用途，尚未达到生产环境可直接部署的医疗系统标准。

## 核心功能

- 通过 `POST /api/agent/query` 提供基于 Qwen 的智能问答入口
- 支持通过患者编号、手机号等信息进行患者查询
- 提供患者、病例、就诊记录的结构化 CRUD 接口
- 支持长期记忆画像、关键事件提取与混合检索
- 提供 React 工作台界面，用于患者概览、聊天、就诊摘要和记忆展示
- 支持图片上传，进行多模态问答
- 使用 SQLite 进行本地数据持久化
- 使用 FAISS 进行长期记忆向量检索

## 技术栈

### 后端

- Python 3.12
- FastAPI
- SQLAlchemy
- Pydantic v2
- SQLite
- FAISS
- OpenAI 兼容 SDK 调用 Qwen / DashScope

### 前端

- React 18
- Vite
- TypeScript
- Tailwind CSS
- TanStack Query
- Zustand

## 架构说明

整个项目可以分为四个主要层次：

1. API 层  
   使用 FastAPI 暴露 Agent、Dashboard、Patients、Visit Records 和 Memory 等接口。

2. Agent 层  
   由 `QwenMCPAgent` 负责组织大模型推理、工具调用、多模态输入处理以及记忆上下文注入。

3. 数据与记忆层  
   使用 SQLite 存储结构化业务数据和对话记录，使用 FAISS 支持长期记忆事件的向量检索。

4. 前端工作台层  
   使用 React 构建患者工作台，展示患者概览、聊天记录、最近就诊摘要和长期记忆信息。

## 项目结构

```text
.
|-- app/                    # FastAPI 应用、路由、服务、数据库、LLM 集成
|   |-- api/routes/         # API 路由定义
|   |-- db/                 # SQLAlchemy 模型、数据库会话、初始化逻辑
|   |-- llm/                # Qwen 客户端与 Agent 编排逻辑
|   |-- schemas/            # Pydantic 数据模型
|   `-- services/           # 业务服务与记忆处理逻辑
|-- data/                   # 本地 SQLite 数据、上传媒体、FAISS 索引文件
|-- docs/                   # PRD 与架构说明文档
|-- frontend/               # React + Vite 前端工程
|   |-- src/
|   `-- package.json
|-- scripts/                # 演示数据与本地测试脚本
|-- .env.example            # 环境变量模板
|-- README.md
`-- requirements.txt
```

## 主要接口

### Agent

- `POST /api/agent/query`
- `GET /api/health`

### Dashboard

- `GET /api/dashboard/patient-overview`

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
conda --no-plugins create --solver=classic -n patientcare-agent-dev python=3.12 -y
conda activate patientcare-agent-dev
```

当然，你也可以使用自己习惯的虚拟环境工具。

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

- `QWEN_BASE_URL`：如果你需要覆盖默认的 DashScope 兼容接口地址，可以额外配置这个变量

### 4. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

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
npm run dev
```

前端地址：

- 工作台：[http://127.0.0.1:5173](http://127.0.0.1:5173)

开发环境下，Vite 会将 `/api` 和 `/media` 请求代理到 `http://127.0.0.1:8000`。

## 本地构建预览

如果你希望由 FastAPI 直接托管前端构建产物，可以先执行：

```bash
cd frontend
npm run build
cd ..
python -m uvicorn app.main:app --reload
```

然后访问：

- [http://127.0.0.1:8000](http://127.0.0.1:8000)

当 `frontend/dist` 存在时，`app.main` 会自动优先托管前端构建后的静态资源。

## 演示数据

项目默认使用本地 SQLite 数据库，路径为：

- `data/patient_agent.db`

如需导入演示数据，可执行：

```bash
sqlite3 data/patient_agent.db < scripts/seed_demo_data.sql
```

如果本机没有安装 `sqlite3`，也可以使用任意 SQLite 可视化工具导入该 SQL 文件。

## 本地测试

项目中提供了一个简单脚本，用于直接测试 Agent：

```bash
python scripts/test_qwen_agent.py "请总结患者 P1001 最近一次就诊记录"
```

如果需要结合图片进行测试：

```bash
python scripts/test_qwen_agent.py "请分析这张图片中的检查信息" --image-file data/example.png
```

## 许可证

本项目采用 MIT License。你可以自由使用、修改和分发代码，但需保留原始许可证声明。
