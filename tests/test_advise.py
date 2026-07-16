"""Node 4 (advise) 单元测试。mock LLM, 只验证节点的装填逻辑与错误处理。"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from jdscout.nodes import advise as advise_module
from jdscout.state import ResumeAdvice, BulletRewrite, GapAnalysis, JDRequirements


def _fake_advice() -> ResumeAdvice:
    return ResumeAdvice(
        should_apply="worth_trying",
        should_apply_reason="匹配度 72, 强项能补缺口。",
        bullet_rewrites=[
            BulletRewrite(
                original="做过一个 Agent 项目",
                rewritten="独立设计并实现基于 LangGraph 的 4 节点 Agent 工作流",
                rationale="突出 JD 要求的 LangGraph 关键词。",
            )
        ],
        interview_prep_focus=["LangGraph checkpointer", "Docker 部署"],
        questions_to_ask_interviewer=["团队现在 Agent 的可观测性怎么做?"],
    )


def _fake_gap() -> GapAnalysis:
    return GapAnalysis(
        overall_match_score=72,
        skill_matches=[],
        strengths=["LangGraph 实战"],
        critical_gaps=["缺 Docker"],
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
    monkeypatch.setattr(advise_module, "get_deepseek_model", lambda: model)
    return structured_model


@pytest.mark.asyncio
async def test_advise_success(monkeypatch):
    fake = _fake_advice()
    sm = _patch_model(monkeypatch, ainvoke_return=fake)

    state = {
        "jd_structured": _fake_jd(),
        "gap_analysis": _fake_gap(),
        "resume_raw_text": "我的简历..." * 20,
    }
    result = await advise_module.advise(state)

    assert result["advice"] is fake
    assert result["advice"].should_apply == "worth_trying"
    sm.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_advise_missing_prerequisites(monkeypatch):
    _patch_model(monkeypatch, ainvoke_return=_fake_advice())

    # 缺 gap_analysis
    result = await advise_module.advise({"jd_structured": _fake_jd()})

    assert "advice" not in result
    assert result["errors"] == ["advise: missing prerequisites (gap_analysis or jd_structured)"]


@pytest.mark.asyncio
async def test_advise_llm_error(monkeypatch):
    _patch_model(monkeypatch, ainvoke_raises=RuntimeError("boom"))

    state = {
        "jd_structured": _fake_jd(),
        "gap_analysis": _fake_gap(),
        "resume_raw_text": "x" * 100,
    }
    result = await advise_module.advise(state)

    assert "advice" not in result
    assert "advise failed" in result["errors"][0]
    assert "boom" in result["errors"][0]
