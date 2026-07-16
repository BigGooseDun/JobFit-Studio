"""Node 4: advise —— 基于 gap 分析生成简历改写建议 + 面试准备重点。

关键决策:
- 三个输入全给(jd_structured + gap_analysis + resume_raw_text): advise 是"综合决策"节点,
  既要知道岗位要什么(jd)、又要知道差距在哪(gap)、还要拿到简历原文才能做 bullet 改写。
- 只 append errors 不 raise(同前几个节点)。
- 同 extract/analyze: method="function_calling"。
"""
from jdscout.config import get_deepseek_model
from jdscout.prompts.templates import ADVISE_PROMPT
from jdscout.state import AgentState, ResumeAdvice


async def advise(state: AgentState) -> dict:
    """基于 gap 分析生成简历改写建议 + 面试准备重点。"""
    if not state.get("gap_analysis") or not state.get("jd_structured"):
        return {"errors": ["advise: missing prerequisites (gap_analysis or jd_structured)"]}

    model = get_deepseek_model()
    structured_model = model.with_structured_output(ResumeAdvice, method="function_calling")

    prompt = ADVISE_PROMPT.format(
        jd=state["jd_structured"].model_dump_json(indent=2),
        gap=state["gap_analysis"].model_dump_json(indent=2),
        resume=state.get("resume_raw_text", ""),
    )
    try:
        result = await structured_model.ainvoke(prompt)
        if result is None:
            # 输出被截断/解析失败时, with_structured_output 可能静默返回 None 而不 raise。
            return {"errors": ["advise failed: model returned no structured output (possibly truncated)"]}
        return {"advice": result}
    except Exception as e:
        return {"errors": [f"advise failed: {e}"]}
