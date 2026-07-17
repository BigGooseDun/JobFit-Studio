"""FastAPI 主入口。

启动:  uv run uvicorn jdscout.api.server:app --reload --port 8000
文档:  http://localhost:8000/docs (Swagger UI, FastAPI 自带)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from jdscout.api.routes import router

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


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """根路径重定向到自带的 Swagger 文档。"""
    return RedirectResponse(url="/docs")
