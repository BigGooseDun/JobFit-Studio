"""Node 4: advise —— 基于 gap 分析 + 相似历史投递生成建议。

关键决策:
- 三个输入全给(jd_structured + gap_analysis + resume_raw_text): advise 是"综合决策"节点。
- RAG: LLM 调用前先检索相似历史投递, 注入 prompt, 让建议参考用户历史模式(复发缺口等)。
  检索失败/为空都不该阻断 advise —— 降级为"无历史上下文"继续。
- 检索结果也塞进 state['similar_histories'], 给前端展示。
- 同 extract/analyze: method="function_calling"。
"""
from jdscout.config import get_deepseek_model
from jdscout.nodes._structured import ainvoke_structured_with_retry
from jdscout.prompts.templates import ADVISE_PROMPT
from jdscout.rag.retriever import find_similar, format_similar_histories_for_prompt
from jdscout.state import AgentState, ResumeAdvice


async def advise(state: AgentState) -> dict:
    """基于 gap 分析 + 相似历史生成简历改写建议 + 面试准备重点。"""
    if not state.get("gap_analysis") or not state.get("jd_structured"):
        return {"errors": ["advise: missing prerequisites (gap_analysis or jd_structured)"]}

    # RAG 检索(失败降级为空, 不阻断)
    try:
        similar = find_similar(state["jd_structured"], top_k=3)
    except Exception:
        similar = []

    model = get_deepseek_model()
    structured_model = model.with_structured_output(ResumeAdvice, method="function_calling")

    prompt = ADVISE_PROMPT.format(
        jd=state["jd_structured"].model_dump_json(indent=2),
        gap=state["gap_analysis"].model_dump_json(indent=2),
        resume=state.get("resume_raw_text", ""),
        similar_histories_context=format_similar_histories_for_prompt(similar),
    )
    try:
        result = await ainvoke_structured_with_retry(structured_model, prompt)
        return {"advice": result, "similar_histories": similar}
    except Exception as e:
        # 即便 advise LLM 失败, 也把检索到的相似历史透出给前端。
        return {"errors": [f"advise failed: {e}"], "similar_histories": similar}
