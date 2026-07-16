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


ANALYZE_PROMPT = """You are comparing a candidate's resume against a structured job description (JD).

JD (structured):
```json
{jd}
```

Resume (raw text):
---
{resume}
---

Your task:
1. For EACH hard_skill in the JD, determine if the resume shows: matched / partial / missing.
   - 'matched': resume explicitly demonstrates this skill (cite the evidence sentence).
   - 'partial': related but not exact (e.g., JD asks React, resume shows Vue — mark partial).
   - 'missing': no evidence in resume.
2. Identify 3-5 strengths where the candidate's resume goes ABOVE the JD requirements.
3. Identify critical_gaps (up to 5) that would materially affect whether to apply.
4. Give overall_match_score 0-100:
   - 90+: strongly matched, almost certain interview
   - 70-89: solid match, worth applying
   - 50-69: stretch, some critical gaps
   - <50: significant mismatch

Be honest. Do not inflate the score to be encouraging."""


ADVISE_PROMPT = """You are a career coach helping a job seeker tailor their resume for a specific JD.

JD (structured):
```json
{jd}
```

Gap Analysis:
```json
{gap}
```

Resume (raw text):
---
{resume}
---

Your task:
1. Decide should_apply:
   - 'strongly_recommend': match_score >= 80, no critical_gaps
   - 'worth_trying': 60-79, some gaps but strengths compensate
   - 'stretch': 50-59, apply only if user has time and confidence
   - 'not_recommended': <50 or has deal-breaking gaps

2. Suggest 3-5 bullet_rewrites:
   - Pick the resume bullets MOST relevant to this JD.
   - Rewrite each to emphasize keywords from the JD (only if the underlying experience is real).
   - IMPORTANT: Do NOT invent achievements. Only rephrase existing bullets to highlight relevant angles.
   - Include a 1-sentence rationale for each rewrite.

3. Suggest 3-5 interview_prep_focus items:
   - Based on the JD requirements + gaps, what tech topics should the candidate deep-review?
   - Be specific (e.g., "Study LangGraph checkpointer & thread persistence" not "Review LangGraph").

4. Suggest 2-3 questions_to_ask_interviewer:
   - Questions that show engagement AND help the candidate assess fit.
   - Avoid generic "what's your culture" questions."""
