"""Node 2 (extract) 单元测试。

原则(蓝图第 13 节): 不在单元测试里调真实 API —— 慢、贵、不稳定。
这里 mock 掉 get_deepseek_model, 只验证 extract 节点的"装填逻辑与错误处理",
不验证 DeepSeek 到底抽得准不准(那是端到端测试的事)。
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from jdscout.nodes import extract as extract_module
from jdscout.state import JDRequirements


def _fake_jd() -> JDRequirements:
    """一个合法的 JDRequirements, 模拟 LLM 抽取成功后的产物。"""
    return JDRequirements(
        role_title="AI Agent 后端工程师",
        company="某 FinTech 公司",
        location="深圳",
        seniority="mid",
        hard_skills=["Python", "LangGraph", "Docker"],
        nice_to_have=["RAG"],
        domain="FinTech",
        years_of_experience="1-3年",
        education="本科",
        salary_range="25-40K·14薪",
        key_responsibilities=["设计 Agent 工作流", "对接 LLM", "部署上线"],
    )


def _patch_model(monkeypatch, *, ainvoke_return=None, ainvoke_raises=None) -> None:
    """把 extract 模块里的 get_deepseek_model 换成假的。

    模拟调用链: get_deepseek_model() -> .with_structured_output(schema) -> .ainvoke(prompt)
    """
    structured_model = MagicMock()
    if ainvoke_raises is not None:
        structured_model.ainvoke = AsyncMock(side_effect=ainvoke_raises)
    else:
        structured_model.ainvoke = AsyncMock(return_value=ainvoke_return)

    model = MagicMock()
    model.with_structured_output.return_value = structured_model

    monkeypatch.setattr(extract_module, "get_deepseek_model", lambda: model)
    return structured_model


@pytest.mark.asyncio
async def test_extract_success(monkeypatch):
    """有 jd_raw_text + LLM 正常返回 -> state 里填上 jd_structured。"""
    fake = _fake_jd()
    structured_model = _patch_model(monkeypatch, ainvoke_return=fake)

    state = {"jd_raw_text": "我们招聘 AI Agent 工程师, 要求 Python/LangGraph..." * 10}
    result = await extract_module.extract(state)

    assert "jd_structured" in result
    assert result["jd_structured"] is fake
    assert result["jd_structured"].hard_skills == ["Python", "LangGraph", "Docker"]
    # 确认真的走了 with_structured_output(JDRequirements) 这条路
    structured_model.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_missing_jd_raw_text(monkeypatch):
    """没有 jd_raw_text -> 不调 LLM, 直接返回 errors。"""
    _patch_model(monkeypatch, ainvoke_return=_fake_jd())

    result = await extract_module.extract({})

    assert "jd_structured" not in result
    assert result["errors"] == ["extract: no jd_raw_text to process"]


@pytest.mark.asyncio
async def test_extract_llm_error(monkeypatch):
    """LLM 抛异常(如超时/校验失败重试耗尽) -> 捕获后写入 errors, 不 raise。"""
    _patch_model(monkeypatch, ainvoke_raises=RuntimeError("boom"))

    state = {"jd_raw_text": "x" * 300}
    result = await extract_module.extract(state)

    assert "jd_structured" not in result
    assert len(result["errors"]) == 1
    assert "extract failed" in result["errors"][0]
    assert "boom" in result["errors"][0]
