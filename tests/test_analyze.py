"""Node 3 (analyze) 单元测试。mock LLM, 只验证节点的装填逻辑与错误处理。"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from jdscout.nodes import analyze as analyze_module
from jdscout.state import GapAnalysis, SkillMatch, JDRequirements


def _fake_gap() -> GapAnalysis:
    return GapAnalysis(
        overall_match_score=72,
        skill_matches=[
            SkillMatch(skill="Python", status="matched", evidence="用 Python 写过 Agent"),
            SkillMatch(skill="Docker", status="missing", evidence=None),
        ],
        strengths=["有 LangGraph 实战", "FinTech 背景"],
        critical_gaps=["缺 Docker 部署经验"],
        minor_gaps=["无 CI/CD"],
    )


def _fake_jd() -> JDRequirements:
    return JDRequirements(
        role_title="AI Agent 工程师",
        seniority="mid",
        hard_skills=["Python", "Docker"],
        key_responsibilities=["搭 Agent"],
    )


def _patch_model(monkeypatch, *, ainvoke_return=None, ainvoke_raises=None):
    structured_model = MagicMock()
    if ainvoke_raises is not None:
        structured_model.ainvoke = AsyncMock(side_effect=ainvoke_raises)
    else:
        structured_model.ainvoke = AsyncMock(return_value=ainvoke_return)
    model = MagicMock()
    model.with_structured_output.return_value = structured_model
    monkeypatch.setattr(analyze_module, "get_deepseek_model", lambda: model)
    return structured_model


@pytest.mark.asyncio
async def test_analyze_success(monkeypatch):
    fake = _fake_gap()
    sm = _patch_model(monkeypatch, ainvoke_return=fake)

    state = {"jd_structured": _fake_jd(), "resume_raw_text": "我的简历..." * 20}
    result = await analyze_module.analyze(state)

    assert result["gap_analysis"] is fake
    assert result["gap_analysis"].overall_match_score == 72
    sm.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_analyze_missing_prerequisites(monkeypatch):
    _patch_model(monkeypatch, ainvoke_return=_fake_gap())

    # 缺 resume_raw_text
    result = await analyze_module.analyze({"jd_structured": _fake_jd()})

    assert "gap_analysis" not in result
    assert result["errors"] == ["analyze: missing prerequisites (jd_structured or resume_raw_text)"]


@pytest.mark.asyncio
async def test_analyze_llm_error(monkeypatch):
    _patch_model(monkeypatch, ainvoke_raises=RuntimeError("boom"))

    state = {"jd_structured": _fake_jd(), "resume_raw_text": "x" * 100}
    result = await analyze_module.analyze(state)

    assert "gap_analysis" not in result
    assert "analyze failed" in result["errors"][0]
    assert "boom" in result["errors"][0]
