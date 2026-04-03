# 作者：小红书@人间清醒的李某人

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.db.init_db import init_db
from app.db.session import DATA_DIR
from app.env import load_env_file


load_env_file()
init_db()
APP_DIR = Path(__file__).resolve().parent
LEGACY_STATIC_DIR = APP_DIR / "static"
FRONTEND_DIST_DIR = APP_DIR.parent / "frontend" / "dist"
STATIC_DIR = FRONTEND_DIST_DIR if FRONTEND_DIST_DIR.exists() else LEGACY_STATIC_DIR
ASSETS_DIR = STATIC_DIR / "assets"

openapi_tags = [
    {
        "name": "Agent",
        "description": "通过 Qwen 大模型结合内部工具进行信息查询。",
    },
    {
        "name": "Patients",
        "description": "患者基础身份信息的创建、读取和更新。",
    },
    {
        "name": "Medical Cases",
        "description": "患者病例信息的创建、读取和更新。",
    },
    {
        "name": "Visit Records",
        "description": "患者就诊记录的创建、读取和更新。",
    },
    {
        "name": "Memory",
        "description": "长期记忆偏好配置的查询与更新。",
    },
]

app = FastAPI(
    title="Patient Agent API",
    version="0.1.0",
    description="患者信息、病例和就诊记录的基础数据服务。",
    openapi_tags=openapi_tags,
)
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
elif LEGACY_STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=LEGACY_STATIC_DIR), name="static")
app.mount("/media", StaticFiles(directory=DATA_DIR), name="media")
app.include_router(router, prefix="/api")


@app.get("/", include_in_schema=False)
def read_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/query", include_in_schema=False)
def read_query_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/chat", include_in_schema=False)
def read_chat_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
