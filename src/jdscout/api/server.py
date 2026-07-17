"""FastAPI 主入口。

启动:  uv run uvicorn jdscout.api.server:app --reload --port 8000
文档:  http://localhost:8000/docs (Swagger UI, FastAPI 自带)
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from jdscout.api.routes import router

# 前端静态文件目录(src/jdscout/web/static)
_STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"

app = FastAPI(
    title="JD-Scout API",
    description="把一份岗位 JD 和你的简历做深度对比, 输出匹配度、改写建议和面试重点。",
    version="0.1.0",
)

# 开发期允许所有 origin, 方便前端本地联调; 生产环境应收紧到白名单。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# 把 css/js 挂到 /static;index.html 单独在 "/" 提供(见下)。
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """前后端同源: FastAPI 直接把前端主页面 serve 在根路径。"""
    return FileResponse(_STATIC_DIR / "index.html")
