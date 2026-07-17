"""API 单元测试。用 TestClient + mock graph, 不调真实 LLM。

PDF 解析走真实的 sample_resume.pdf(本地、快、不花钱), 只 mock 掉 LLM 相关的 graph。
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from jdscout.api import routes as routes_module
from jdscout.api.server import app
from jdscout.state import JDRequirements, GapAnalysis, ResumeAdvice, BulletRewrite

client = TestClient(app)

RESUME = "examples/sample_resume.pdf"


def _fake_final_state() -> dict:
    return {
        "jd_structured": JDRequirements(
            role_title="AI Agent 工程师", seniority="mid",
            hard_skills=["Python", "LangGraph"], key_responsibilities=["搭 Agent"],
        ),
        "gap_analysis": GapAnalysis(
            overall_match_score=78, skill_matches=[], strengths=["LangGraph 实战"],
            critical_gaps=["缺 Docker"],
        ),
        "advice": ResumeAdvice(
            should_apply="worth_trying", should_apply_reason="匹配度高",
            bullet_rewrites=[BulletRewrite(original="a", rewritten="b", rationale="c")],
            interview_prep_focus=["LangGraph"],
        ),
        "errors": [],
    }


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_analyze_success(monkeypatch):
    fake_graph = MagicMock()
    fake_graph.ainvoke = AsyncMock(return_value=_fake_final_state())
    monkeypatch.setattr(routes_module, "graph", fake_graph)

    with open(RESUME, "rb") as f:
        resp = client.post(
            "/api/analyze",
            data={"jd_text": "我们招聘 AI Agent 工程师, 要求 Python/LangGraph 经验..."},
            files={"resume_file": ("sample_resume.pdf", f, "application/pdf")},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["jd"]["role_title"] == "AI Agent 工程师"
    assert body["gap"]["overall_match_score"] == 78
    assert body["advice"]["should_apply"] == "worth_trying"
    assert body["errors"] == []
    fake_graph.ainvoke.assert_awaited_once()


def test_analyze_rejects_non_pdf(monkeypatch):
    fake_graph = MagicMock()
    fake_graph.ainvoke = AsyncMock(return_value=_fake_final_state())
    monkeypatch.setattr(routes_module, "graph", fake_graph)

    resp = client.post(
        "/api/analyze",
        data={"jd_text": "some jd text here long enough"},
        files={"resume_file": ("resume.txt", b"not a pdf", "text/plain")},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["type"] == "invalid_file"


def test_analyze_missing_jd_text():
    # 缺 jd_text(Form required)-> FastAPI 校验返回 422
    with open(RESUME, "rb") as f:
        resp = client.post(
            "/api/analyze",
            files={"resume_file": ("sample_resume.pdf", f, "application/pdf")},
        )
    assert resp.status_code == 422


def test_analyze_bad_pdf_bytes(monkeypatch):
    fake_graph = MagicMock()
    fake_graph.ainvoke = AsyncMock(return_value=_fake_final_state())
    monkeypatch.setattr(routes_module, "graph", fake_graph)

    # .pdf 扩展名但内容不是 PDF -> pdfplumber 解析失败 -> 400 pdf_parse_error
    resp = client.post(
        "/api/analyze",
        data={"jd_text": "some jd text here long enough"},
        files={"resume_file": ("fake.pdf", b"%PDF-broken-garbage", "application/pdf")},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["type"] == "pdf_parse_error"


def test_analyze_stream_emits_events(monkeypatch):
    """mock astream_events, 验证 SSE 输出 node_start/node_end/final_result。"""
    async def fake_events(initial_state, version=None):
        yield {"event": "on_chain_start", "name": "extract",
               "metadata": {"langgraph_node": "extract"}, "data": {}}
        yield {"event": "on_chain_end", "name": "extract",
               "metadata": {"langgraph_node": "extract"}, "data": {"output": {}}}
        yield {"event": "on_chain_end", "name": "LangGraph",
               "metadata": {}, "data": {"output": _fake_final_state()}}

    fake_graph = MagicMock()
    fake_graph.astream_events = fake_events
    monkeypatch.setattr(routes_module, "graph", fake_graph)

    with open(RESUME, "rb") as f:
        resp = client.post(
            "/api/analyze/stream",
            data={"jd_text": "我们招聘 AI Agent 工程师..."},
            files={"resume_file": ("sample_resume.pdf", f, "application/pdf")},
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    text = resp.text
    assert "event: node_start" in text
    assert "event: node_end" in text
    assert "event: final_result" in text
    assert "worth_trying" in text
