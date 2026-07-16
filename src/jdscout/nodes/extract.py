"""Node 2: extract —— 从 JD 原文抽取结构化需求(JDRequirements)。

关键决策:
- 用 .with_structured_output(JDRequirements): 让 LangChain 把 Pydantic schema 转成
  模型的 function-calling / json schema, 模型输出会被强制校验成 JDRequirements 实例。
  不符合会自动 retry —— 这是"反幻觉 + 数据可预期"的核心机制。
- 错误只往 state['errors'] append, 不 raise: 和 fetch_jd 同理, 让整张图跑完、
  由上层决定如何呈现, 而不是中途炸掉。
"""
from jdscout.config import get_deepseek_model
from jdscout.prompts.templates import EXTRACT_JD_PROMPT
from jdscout.state import AgentState, JDRequirements


async def extract(state: AgentState) -> dict:
    """从 JD 原文抽取结构化需求。"""
    if not state.get("jd_raw_text"):
        return {"errors": ["extract: no jd_raw_text to process"]}

    model = get_deepseek_model()
    # method="function_calling": langchain-openai 1.x 默认用 method="json_schema"
    # (OpenAI 的 structured outputs, 走 response_format), 但 DeepSeek 的 OpenAI-compatible
    # 端点不支持它, 会返回 400 "This response_format type is unavailable now"。
    # DeepSeek 支持 function/tool calling, 所以显式改用 function_calling 让 schema 通过
    # tool 参数下发。(对应蓝图第 15 节的已知坑。)
    structured_model = model.with_structured_output(JDRequirements, method="function_calling")

    prompt = EXTRACT_JD_PROMPT.format(jd_text=state["jd_raw_text"])
    try:
        result = await structured_model.ainvoke(prompt)
        if result is None:
            # 输出被截断/解析失败时, with_structured_output 可能静默返回 None 而不 raise。
            return {"errors": ["extract failed: model returned no structured output (possibly truncated)"]}
        return {"jd_structured": result}
    except Exception as e:
        return {"errors": [f"extract failed: {e}"]}
