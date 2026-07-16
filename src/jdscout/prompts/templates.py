"""4 个节点的 prompt 模板。Milestone 2 先只写 EXTRACT_JD_PROMPT。

prompt 设计原则(贯穿全部节点):
- 明确 "Do NOT invent" —— 反幻觉(LLM 会脑补 JD 里没写的技能)
- 明确 "use null / empty list" —— 缺失字段有确定行为, 不让模型瞎填
- 只抽硬技能, 排除软技能 —— 下游 gap 分析才有意义
"""

EXTRACT_JD_PROMPT = """You are analyzing a job description (JD) to extract structured requirements.

Extract the following from the JD text below. Be precise and faithful to what's written:

- Do NOT invent skills or requirements not mentioned in the JD.
- If a field is not mentioned, use null (for optional fields) or an empty list.
- For hard_skills: extract concrete technical skills only (languages, frameworks, tools, protocols). Do not include soft skills.
- For nice_to_have: things explicitly marked as "加分项" / "preferred" / "bonus" / "plus".
- For key_responsibilities: 5-10 concrete bullet items describing the day-to-day work.

JD text:
---
{jd_text}
---

Extract now."""
