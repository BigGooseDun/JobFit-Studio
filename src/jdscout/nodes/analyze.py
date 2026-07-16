"""Node 3: analyze —— 对比 JD 需求 vs 简历原文, 输出 gap 分析。

关键决策:
- 输入用 state['jd_structured'](Node 2 的结构化产出)而不是 jd_raw_text: 结构化后
  字段清晰, 模型对比时不用再从原文里"找需求", 更聚焦、更准。
- 简历用 raw_text(未结构化): 简历格式千差万别, 强行结构化反而丢信息; 让模型直接读
  全文去找证据(evidence)更灵活。
- 同 extract: method="function_calling"(DeepSeek 不支持默认的 json_schema)。
"""
from jdscout.config import get_deepseek_model
from jdscout.prompts.templates import ANALYZE_PROMPT
from jdscout.state import AgentState, GapAnalysis


async def analyze(state: AgentState) -> dict:
    """对比 JD 需求 vs 简历原文, 输出 gap 分析。"""
    if not state.get("jd_structured") or not state.get("resume_raw_text"):
        return {"errors": ["analyze: missing prerequisites (jd_structured or resume_raw_text)"]}

    model = get_deepseek_model()
    structured_model = model.with_structured_output(GapAnalysis, method="function_calling")

    # model_dump_json: 把 JDRequirements 对象序列化成规整 JSON 塞进 prompt,
    # 字段名清晰、模型读得稳(见 02-notes 决策)。
    prompt = ANALYZE_PROMPT.format(
        jd=state["jd_structured"].model_dump_json(indent=2),
        resume=state["resume_raw_text"],
    )
    try:
        result = await structured_model.ainvoke(prompt)
        return {"gap_analysis": result}
    except Exception as e:
        return {"errors": [f"analyze failed: {e}"]}
