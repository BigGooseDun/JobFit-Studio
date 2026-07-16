"""端到端测试(真实调用 DeepSeek)。

默认跳过 —— 它会真的调 API(慢、花钱、依赖网络), 不该进 CI 常规跑。
需要时手动开:

    RUN_E2E=1 uv run pytest tests/test_e2e.py -v

前置: .env 里填好 DEEPSEEK_API_KEY, examples/sample_resume.pdf 存在。
"""
import os

import pytest

from jdscout.cli import run
from jdscout.state import ResumeAdvice

_SHOULD_APPLY_ENUM = {"strongly_recommend", "worth_trying", "stretch", "not_recommended"}

SAMPLE_JD = """
【岗位】AI Agent 工程师(深圳 · 南山)
【公司】某持牌金融科技公司(FinTech)
【薪资】30-50K·15薪
【岗位职责】
1. 基于 LangGraph 构建多节点 Agent 工作流;
2. 设计 Prompt 与 Function Calling, 做工具编排;
3. 用 Pydantic 对 LLM 输出做结构化约束;
4. 搭建 RAG 检索链路;
5. 负责服务 Docker 化部署与线上稳定性。
【任职要求】
1. 本科及以上, 1-3 年后端/AI 应用经验;
2. 精通 Python, 熟悉 async;
3. 有 LangChain / LangGraph 实战;
4. 熟悉向量数据库;
5. 熟悉 Docker, 了解 CI/CD。
"""


@pytest.mark.skipif(
    os.getenv("RUN_E2E") != "1",
    reason="端到端测试需真实 API, 设 RUN_E2E=1 才跑",
)
@pytest.mark.asyncio
async def test_full_pipeline_produces_valid_advice():
    report = await run(SAMPLE_JD, "examples/sample_resume.pdf")

    assert report["errors"] == [], f"不应有错误: {report['errors']}"
    assert report["jd"] is not None
    assert report["gap"] is not None
    assert report["advice"] is not None

    # advice 的 should_apply 必须是四个枚举之一(而不是模型自由发挥)
    assert report["advice"]["should_apply"] in _SHOULD_APPLY_ENUM
    # 匹配度分数应在合法区间
    assert 0 <= report["gap"]["overall_match_score"] <= 100
    # 报告 dict 能被 ResumeAdvice 反序列化回来(schema 一致性)
    ResumeAdvice(**report["advice"])
