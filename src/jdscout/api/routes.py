"""API 路由定义。复用现有的 pdf_parser 和 graph, 不重写核心逻辑。"""
import json
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from jdscout.graph import graph
from jdscout.tools.pdf_parser import extract_pdf_text
from jdscout.api.schemas import AnalyzeResponse

router = APIRouter()

# 主图里的 4 个节点名, 用来从 astream_events 的海量事件里筛出"节点边界"。
_NODE_NAMES = {"fetch_jd", "extract", "analyze", "advise"}


async def _resume_text_from_upload(resume_file: UploadFile) -> str:
    """把上传的 PDF 存到临时文件、解析成文本、随即删除(不持久化, 隐私红线 3.4)。"""
    filename = resume_file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail={"type": "invalid_file", "message": "resume_file 必须是 PDF"})

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    try:
        tmp.write(await resume_file.read())
        tmp.flush()
        tmp.close()
        try:
            return extract_pdf_text(Path(tmp.name))
        except Exception as e:
            raise HTTPException(status_code=400, detail={"type": "pdf_parse_error", "message": str(e)})
    finally:
        os.unlink(tmp.name)  # 处理完立即删掉, 不留用户简历


def _assemble_report(final_state: dict) -> dict:
    """把图的最终 state 组装成对外报告(和 CLI / sample_output.json 一致)。"""
    return {
        "jd": final_state["jd_structured"].model_dump() if final_state.get("jd_structured") else None,
        "gap": final_state["gap_analysis"].model_dump() if final_state.get("gap_analysis") else None,
        "advice": final_state["advice"].model_dump() if final_state.get("advice") else None,
        "errors": final_state.get("errors", []),
    }


def _sse(event_type: str, data: dict) -> str:
    """格式化一条 SSE 消息: event: <type>\\n data: <json>\\n\\n。"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/health")
async def health() -> dict:
    """健康检查。"""
    return {"status": "ok"}


@router.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_endpoint(
    jd_text: str = Form(..., description="JD 原文(前端先自行抓取)"),
    resume_file: UploadFile = File(..., description="简历 PDF"),
) -> AnalyzeResponse:
    """一次性分析: 跑完整张图, 返回和 CLI 相同形状的 JSON。"""
    if len(jd_text.strip()) < 1:
        raise HTTPException(status_code=400, detail={"type": "invalid_input", "message": "jd_text 不能为空"})

    resume_text = await _resume_text_from_upload(resume_file)
    initial_state = {"jd_input": jd_text, "resume_raw_text": resume_text}

    try:
        final_state = await graph.ainvoke(initial_state)
    except Exception as e:  # 意外崩溃 → 500
        raise HTTPException(status_code=500, detail={"type": "internal_error", "message": str(e)})

    # 图正常跑完即 200; 节点级的软错误(如某节点失败)随 errors 数组透出, 和 CLI 行为一致。
    return AnalyzeResponse(
        jd=final_state.get("jd_structured"),
        gap=final_state.get("gap_analysis"),
        advice=final_state.get("advice"),
        errors=final_state.get("errors", []),
    )


@router.post("/api/analyze/stream")
async def analyze_stream_endpoint(
    jd_text: str = Form(..., description="JD 原文"),
    resume_file: UploadFile = File(..., description="简历 PDF"),
) -> StreamingResponse:
    """流式分析: 用 astream_events 实时推送每个节点的 start/end, 最后推 final_result。

    事件类型: node_start / node_end / final_result / error。
    """
    if len(jd_text.strip()) < 1:
        raise HTTPException(status_code=400, detail={"type": "invalid_input", "message": "jd_text 不能为空"})

    # PDF 解析放在开始流式之前, 这样解析错误能以 400 立刻返回, 而不是塞进事件流。
    resume_text = await _resume_text_from_upload(resume_file)
    initial_state = {"jd_input": jd_text, "resume_raw_text": resume_text}

    async def event_generator():
        final_output: dict = {}
        try:
            async for ev in graph.astream_events(initial_state, version="v2"):
                kind = ev["event"]
                name = ev.get("name")
                meta = ev.get("metadata", {}) or {}

                if name in _NODE_NAMES and kind == "on_chain_start":
                    yield _sse("node_start", {"node": name})
                elif name in _NODE_NAMES and kind == "on_chain_end":
                    yield _sse("node_end", {"node": name})

                # 最外层图(没有 langgraph_node 元数据)的 on_chain_end 带着最终 state
                if kind == "on_chain_end" and not meta.get("langgraph_node"):
                    output = ev.get("data", {}).get("output")
                    if isinstance(output, dict):
                        final_output = output

            yield _sse("final_result", _assemble_report(final_output))
        except Exception as e:
            yield _sse("error", {"type": "internal_error", "message": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")
