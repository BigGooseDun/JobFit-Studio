# PHASE 1 蓝图 — MVP: LangGraph 4 节点工作流

> 这份文档给 Claude Code 看的,是 Phase 1(MVP)的**具体实施方案**。读完 `PROJECT_NOTES.md` 之后再读这个。所有代码骨架、schema 定义、prompt 模板都在这里。

---

## 0. Phase 1 完成标准

- [ ] `python -m jdscout.cli --jd <URL_or_TEXT> --resume <PDF_path>` 能跑通完整流程
- [ ] 输出一份结构化 JSON 报告(见第 6 节 schema)
- [ ] 4 个节点每个都有对应的单元测试(用 fixture,不调真实 API)
- [ ] 一个真实端到端测试:用 sample JD + Ziming 自己的简历跑通
- [ ] Docker 能 build 起来
- [ ] README(英文)基础版完成

---

## 1. 端到端数据流

```
┌──────────────────────────────────────────────────────────────────────┐
│  CLI 入口 (jdscout.cli):                                              │
│    输入: --jd <URL_or_TEXT> --resume <PDF_path>                       │
│    → 读取 PDF 简历 → 提取纯文本                                        │
│    → 抓取 JD (如果是 URL) → 提取纯文本                                 │
│    → 调用 graph.ainvoke(initial_state)                                │
│    → 输出 JSON 报告                                                    │
└──────────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│  LangGraph 主图 (jdscout.graph):                                      │
│                                                                        │
│    START → fetch_jd → extract → analyze → advise → END                │
│                                                                        │
│  State (jdscout.state):                                               │
│    jd_raw_text:       JD 原始文本                                      │
│    resume_raw_text:   简历原始文本                                     │
│    jd_structured:     JDRequirements (Pydantic, Node 2 产出)          │
│    gap_analysis:      GapAnalysis (Pydantic, Node 3 产出)             │
│    advice:            ResumeAdvice (Pydantic, Node 4 产出)            │
└──────────────────────────────────────────────────────────────────────┘

  Node 1: fetch_jd
    Input:  URL or raw text (state.jd_raw_text 可能已经填了)
    Logic:  如果 state.jd_raw_text 已有,跳过;如果只有 URL,调用 web_scraper 工具
            fallback: 抓不到时报错,让用户手动粘贴
    Output: state.jd_raw_text (纯文本)

  Node 2: extract
    Input:  state.jd_raw_text
    LLM:    DeepSeek + structured output (Pydantic: JDRequirements)
    Output: state.jd_structured

  Node 3: analyze
    Input:  state.jd_structured + state.resume_raw_text
    LLM:    DeepSeek + structured output (Pydantic: GapAnalysis)
    Output: state.gap_analysis

  Node 4: advise
    Input:  state.jd_structured + state.gap_analysis + state.resume_raw_text
    LLM:    DeepSeek + structured output (Pydantic: ResumeAdvice)
    Output: state.advice
```

---

## 2. State 定义

```python
# src/jdscout/state.py
from typing import Optional, Annotated
from typing_extensions import TypedDict
from pydantic import BaseModel, Field


# ---------- Pydantic Schemas (LLM 结构化输出必须符合) ----------

class JDRequirements(BaseModel):
    """从 JD 抽取的结构化需求"""
    role_title: str = Field(description="岗位名称,例如 'AI Agent 后端工程师'")
    company: Optional[str] = Field(default=None, description="公司名称,如未提及则 null")
    location: Optional[str] = Field(default=None, description="工作地点")
    seniority: str = Field(description="资历要求: 'intern' / 'junior' / 'mid' / 'senior' / 'unspecified'")

    hard_skills: list[str] = Field(
        description="必须掌握的硬技能, 如 ['Python', 'LangGraph', 'Docker']"
    )
    nice_to_have: list[str] = Field(
        default_factory=list, description="加分项技能"
    )
    domain: Optional[str] = Field(
        default=None, description="业务领域, 如 'FinTech' / 'E-commerce' / 'Enterprise SaaS'"
    )
    years_of_experience: Optional[str] = Field(
        default=None, description="经验年限要求, 例如 '1-3年' / '3-5年' / '应届' "
    )
    education: Optional[str] = Field(
        default=None, description="学历要求, 例如 '本科' / '硕士优先'"
    )
    salary_range: Optional[str] = Field(
        default=None, description="薪资范围, 例如 '15-25K·14薪'"
    )
    key_responsibilities: list[str] = Field(
        description="核心工作职责列表, 5-10 条"
    )


class SkillMatch(BaseModel):
    """单个技能的匹配情况"""
    skill: str
    status: str = Field(description="'matched' / 'partial' / 'missing'")
    evidence: Optional[str] = Field(
        default=None,
        description="如果 matched, 引用简历里的哪句话作为证据"
    )


class GapAnalysis(BaseModel):
    """简历 vs JD 的差距分析"""
    overall_match_score: int = Field(
        description="总体匹配度 0-100 分", ge=0, le=100
    )
    skill_matches: list[SkillMatch] = Field(
        description="每个硬技能的匹配情况"
    )
    strengths: list[str] = Field(
        description="简历相对于 JD 的强项, 3-5 条"
    )
    critical_gaps: list[str] = Field(
        description="关键缺口 (会影响是否值得投递), 最多 5 条"
    )
    minor_gaps: list[str] = Field(
        default_factory=list, description="次要缺口"
    )


class BulletRewrite(BaseModel):
    """针对简历某条 bullet 的改写建议"""
    original: str = Field(description="简历原文摘录 (不改动)")
    rewritten: str = Field(description="改写后的版本")
    rationale: str = Field(description="为什么这样改, 1-2 句话")


class ResumeAdvice(BaseModel):
    """给用户的最终建议"""
    should_apply: str = Field(
        description="'strongly_recommend' / 'worth_trying' / 'stretch' / 'not_recommended'"
    )
    should_apply_reason: str = Field(description="为什么建议这样, 2-3 句话")
    bullet_rewrites: list[BulletRewrite] = Field(
        description="针对当前 JD 的简历 bullet 改写建议, 3-5 条"
    )
    interview_prep_focus: list[str] = Field(
        description="面试重点准备的技术点, 3-5 条"
    )
    questions_to_ask_interviewer: list[str] = Field(
        default_factory=list,
        description="反问面试官的问题, 2-3 条"
    )


# ---------- LangGraph State ----------

class AgentState(TypedDict, total=False):
    """整个工作流共享的 state"""
    # 输入
    jd_input: str              # 原始输入: URL 或纯文本
    resume_raw_text: str       # 从 PDF 解析出的简历纯文本

    # 中间状态
    jd_raw_text: str           # Node 1 输出

    # 结构化产出
    jd_structured: JDRequirements    # Node 2 输出
    gap_analysis: GapAnalysis         # Node 3 输出
    advice: ResumeAdvice              # Node 4 输出

    # 元信息
    errors: list[str]          # 每个节点如果出错, append 错误信息
```

---

## 3. 各节点详细设计

### Node 1: fetch_jd (`src/jdscout/nodes/fetch_jd.py`)

```python
async def fetch_jd(state: AgentState) -> dict:
    """获取 JD 纯文本。

    分支:
      1. 如果 state['jd_input'] 是 URL: 调 web_scraper 抓
      2. 如果 state['jd_input'] 是纯文本 (>200 chars): 直接用
      3. 其他 (URL 抓不到 / 太短): raise 让用户手动粘贴

    不用 LLM, 只是 IO + 简单启发式判断
    """
    jd_input = state['jd_input']
    if jd_input.startswith(('http://', 'https://')):
        try:
            text = await web_scraper.fetch_and_extract(jd_input)
            if len(text) < 200:
                raise ValueError("Fetched content too short, likely blocked")
        except Exception as e:
            return {"errors": [f"JD fetch failed: {e}. Please paste JD text directly."]}
    else:
        text = jd_input  # 假设是原文
        if len(text) < 200:
            return {"errors": ["JD text too short (<200 chars). Provide full JD."]}
    return {"jd_raw_text": text}
```

**关键决策**:
- 不用 LLM,纯 IO + 简单判断,快
- 失败时不 raise,而是往 state 里塞 error(让上层 CLI 决定怎么处理)

---

### Node 2: extract (`src/jdscout/nodes/extract.py`)

```python
async def extract(state: AgentState) -> dict:
    """从 JD 原文抽取结构化需求 (JDRequirements)。"""
    if not state.get('jd_raw_text'):
        return {"errors": ["extract: no jd_raw_text to process"]}

    model = get_deepseek_model()  # 见 config.py
    structured_model = model.with_structured_output(JDRequirements)

    prompt = EXTRACT_JD_PROMPT.format(jd_text=state['jd_raw_text'])
    try:
        result = await structured_model.ainvoke(prompt)
        return {"jd_structured": result}
    except Exception as e:
        return {"errors": [f"extract failed: {e}"]}
```

**关键决策**:
- 用 `.with_structured_output(JDRequirements)`,自动处理 Pydantic 校验和 retry
- Prompt 见第 4 节

---

### Node 3: analyze (`src/jdscout/nodes/analyze.py`)

```python
async def analyze(state: AgentState) -> dict:
    """对比 JD 需求 vs 简历原文, 输出 gap 分析。"""
    if not state.get('jd_structured') or not state.get('resume_raw_text'):
        return {"errors": ["analyze: missing prerequisites"]}

    model = get_deepseek_model()
    structured_model = model.with_structured_output(GapAnalysis)

    prompt = ANALYZE_PROMPT.format(
        jd=state['jd_structured'].model_dump_json(indent=2),
        resume=state['resume_raw_text']
    )
    try:
        result = await structured_model.ainvoke(prompt)
        return {"gap_analysis": result}
    except Exception as e:
        return {"errors": [f"analyze failed: {e}"]}
```

---

### Node 4: advise (`src/jdscout/nodes/advise.py`)

```python
async def advise(state: AgentState) -> dict:
    """基于 gap 分析生成简历改写建议 + 面试准备重点。"""
    if not state.get('gap_analysis'):
        return {"errors": ["advise: missing gap_analysis"]}

    model = get_deepseek_model()
    structured_model = model.with_structured_output(ResumeAdvice)

    prompt = ADVISE_PROMPT.format(
        jd=state['jd_structured'].model_dump_json(indent=2),
        gap=state['gap_analysis'].model_dump_json(indent=2),
        resume=state['resume_raw_text']
    )
    try:
        result = await structured_model.ainvoke(prompt)
        return {"advice": result}
    except Exception as e:
        return {"errors": [f"advise failed: {e}"]}
```

---

## 4. Prompt 设计(全部放 `src/jdscout/prompts/templates.py`)

### EXTRACT_JD_PROMPT

```python
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
```

### ANALYZE_PROMPT

```python
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
```

### ADVISE_PROMPT

```python
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
```

**关键 prompt 设计原则**:
- 明确 "Do NOT invent" —— 反幻觉
- 明确 "Cite evidence" —— 引用溯源
- 明确 "Be honest, do not inflate" —— 反谄媚
- 给具体的例子(90+ / 70-89 / 50-69 / <50)让模型 calibrate

---

## 5. 主图组装 (`src/jdscout/graph.py`)

```python
from langgraph.graph import StateGraph, START, END
from jdscout.state import AgentState
from jdscout.nodes.fetch_jd import fetch_jd
from jdscout.nodes.extract import extract
from jdscout.nodes.analyze import analyze
from jdscout.nodes.advise import advise


def build_graph():
    """构建 JD-Scout 主图: fetch_jd → extract → analyze → advise。"""
    builder = StateGraph(AgentState)

    builder.add_node("fetch_jd", fetch_jd)
    builder.add_node("extract", extract)
    builder.add_node("analyze", analyze)
    builder.add_node("advise", advise)

    builder.add_edge(START, "fetch_jd")
    builder.add_edge("fetch_jd", "extract")
    builder.add_edge("extract", "analyze")
    builder.add_edge("analyze", "advise")
    builder.add_edge("advise", END)

    return builder.compile()


# 全局实例, CLI 和后续 web server 都用它
graph = build_graph()
```

**MVP 阶段不加 checkpointer**(内存跑就行)。Phase 2 加 web UI 时再加 `MemorySaver`,实现断点续跑。

---

## 6. CLI 入口 (`src/jdscout/cli.py`)

```python
"""CLI 入口: python -m jdscout.cli --jd <URL_or_TEXT> --resume <PDF_path>"""
import argparse
import asyncio
import json
from pathlib import Path

from jdscout.graph import graph
from jdscout.tools.pdf_parser import extract_pdf_text


async def run(jd_input: str, resume_pdf: Path) -> dict:
    resume_text = extract_pdf_text(resume_pdf)
    initial_state = {
        "jd_input": jd_input,
        "resume_raw_text": resume_text,
    }
    final_state = await graph.ainvoke(initial_state)

    # 组装输出报告
    report = {
        "jd": final_state.get("jd_structured").model_dump() if final_state.get("jd_structured") else None,
        "gap": final_state.get("gap_analysis").model_dump() if final_state.get("gap_analysis") else None,
        "advice": final_state.get("advice").model_dump() if final_state.get("advice") else None,
        "errors": final_state.get("errors", []),
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="JD-Scout: analyze a JD against your resume")
    parser.add_argument("--jd", required=True, help="JD URL or raw text")
    parser.add_argument("--resume", required=True, type=Path, help="Path to resume PDF")
    parser.add_argument("--output", type=Path, help="Save report to file (JSON)")
    args = parser.parse_args()

    report = asyncio.run(run(args.jd, args.resume))
    output_str = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(output_str, encoding="utf-8")
        print(f"Report saved to {args.output}")
    else:
        print(output_str)


if __name__ == "__main__":
    main()
```

---

## 7. 工具:PDF 解析 (`src/jdscout/tools/pdf_parser.py`)

```python
"""PDF 简历解析工具。用 pdfplumber,处理多列排版好于 pypdf。"""
from pathlib import Path
import pdfplumber


def extract_pdf_text(pdf_path: Path) -> str:
    """提取 PDF 全文,页与页之间用空行分隔。"""
    if not pdf_path.exists():
        raise FileNotFoundError(f"Resume PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected .pdf file, got {pdf_path.suffix}")

    texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            texts.append(page_text.strip())
    return "\n\n".join(t for t in texts if t)
```

**MVP 限制**:
- 只支持文字版 PDF,不支持扫描版(需要 OCR,Phase 2 再加)
- 假设简历是单列排版,双列/图片版可能失败(降级方案:让用户改成 docx→pdf 单列版)

---

## 8. 工具:网页抓取 (`src/jdscout/tools/web_scraper.py`)

```python
"""JD 网页抓取。轻量版:requests + BeautifulSoup。
后续如果遇到 JS 渲染的网站(BOSS 直聘等),再加 Playwright fallback。"""
import asyncio
import httpx
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


async def fetch_and_extract(url: str, timeout: int = 15) -> str:
    """抓取 URL, 提取主要文本内容。

    策略:
      1. 用 httpx 异步请求, 15 秒超时
      2. 用 BeautifulSoup 解析, 去掉 script/style/nav/footer
      3. 提取剩余的可见文本

    抓不到就 raise, 上层 fetch_jd 节点决定怎么处理。
    """
    async with httpx.AsyncClient(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # 去掉不需要的标签
    for tag in soup(["script", "style", "nav", "footer", "aside", "header"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    # 折叠连续空行
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)
```

**MVP 已知限制**(README 里要写清楚):
- BOSS 直聘、LinkedIn 等动态渲染网站抓不到 → **让用户手动粘贴 JD 文本**
- 反爬:有些站点会 403,同上,让用户手动粘贴
- **Phase 2 可选**:加 Playwright fallback,处理动态站点

---

## 9. Config (`src/jdscout/config.py`)

```python
"""配置管理。所有 API key/model 从环境变量读, 不硬编码。"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def get_deepseek_model(temperature: float = 0.3, max_tokens: int = 4096):
    """返回配置好的 DeepSeek 客户端。

    用 OpenAI-compatible 接口(DeepSeek 官方支持),这样以后换模型只需要改这个函数。
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set. Copy .env.example to .env and fill it.")

    return ChatOpenAI(
        model="deepseek-chat",
        api_key=api_key,
        base_url="https://api.deepseek.com/v1",
        temperature=temperature,
        max_tokens=max_tokens,
    )
```

**关键**:不要在 Config 里 print API key 任何片段(踩过坑)。

---

## 10. `.env.example`

```bash
# DeepSeek API key. Get one at https://platform.deepseek.com
DEEPSEEK_API_KEY=your_api_key_here

# (可选) OpenAI as fallback
# OPENAI_API_KEY=

# (可选) LangSmith tracing
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_API_KEY=
# LANGCHAIN_PROJECT=jdscout
```

---

## 11. `pyproject.toml`(用 uv 或 poetry 管理)

```toml
[project]
name = "jdscout"
version = "0.1.0"
description = "AI-powered JD analysis agent for job seekers"
requires-python = ">=3.11"
dependencies = [
    "langgraph>=0.2.0",
    "langchain>=0.3.0",
    "langchain-openai>=0.2.0",
    "pydantic>=2.0",
    "python-dotenv>=1.0",
    "pdfplumber>=0.11",
    "httpx>=0.27",
    "beautifulsoup4>=4.12",
    "lxml>=5.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.6",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/jdscout"]
```

---

## 12. Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 依赖
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# 源码
COPY src/ ./src/

# 环境变量占位
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "jdscout.cli"]
```

`docker compose up jdscout --jd "..." --resume "/data/resume.pdf"` 类的用法。

---

## 13. 测试策略

### 单元测试

- `tests/test_fetch.py`:mock `httpx` 返回一段假 HTML,验证 `fetch_and_extract` 提取干净
- `tests/test_extract.py`:mock LLM 返回符合 JDRequirements 的 JSON,验证 node 能正确装填 state
- `tests/test_analyze.py`:同上,mock LLM 返回 GapAnalysis
- `tests/test_advise.py`:同上

**不要在单元测试里调真实 API**(慢、贵、不稳定)。

### 端到端测试

- `tests/test_e2e.py`(可选,单独跑):
  - 用 `examples/sample_jd.txt` 作为 JD
  - 用 `examples/sample_resume.pdf`(Ziming 自己脱敏版简历)
  - 跑完整 graph,断言 `advice.should_apply` 是四个 enum 之一
  - 需要真实 DeepSeek key,不进 CI

---

## 14. 里程碑与检查点

### Milestone 1(Day 1-2):环境 + 骨架
- [ ] 目录结构建好
- [ ] `pyproject.toml` + `uv sync` 装完依赖
- [ ] `.env.example` 完成,`.gitignore` 检查
- [ ] 最简 hello world 图跑通(1 节点,写死输入输出)

### Milestone 2(Day 3-4):Node 1 + Node 2
- [ ] `web_scraper.py` 抓一个真实招聘网页(选一个 requests 能抓的,比如 lever.co 或 boss 直聘的手动粘贴文本)
- [ ] `pdf_parser.py` 解析 Ziming 自己的简历,验证文本抽取
- [ ] Node 1: fetch_jd 通过单元测试
- [ ] Node 2: extract 通过 mock 测试,并且用真实 LLM 跑一遍(输出 JDRequirements JSON)

### Milestone 3(Day 5-6):Node 3 + Node 4
- [ ] Node 3: analyze 通过测试,真实 LLM 输出 GapAnalysis
- [ ] Node 4: advise 通过测试,真实 LLM 输出 ResumeAdvice
- [ ] 主图 build_graph() 组装成功

### Milestone 4(Day 7):端到端 + CLI
- [ ] CLI 跑通:`python -m jdscout.cli --jd <url> --resume ./my_resume.pdf`
- [ ] 输出格式化的 JSON 报告
- [ ] Docker build 成功,`docker run` 跑通
- [ ] README 基础版完成

### Milestone 5(Day 8-9,可选):打磨
- [ ] `--output report.json` 保存到文件
- [ ] 输出 Markdown 格式的报告(方便直接看)
- [ ] Prompt 微调(用 Ziming 自己的几份真实 JD 反复调优)

---

## 15. 常见坑

- **`structured_output` 在 LangChain 里的行为不同 LLM 有差异**:DeepSeek 有时会返回 JSON in markdown code fence,`.with_structured_output()` 一般会处理,但如果失败,考虑用 `PydanticOutputParser` + `format_instructions`
- **DeepSeek `max_tokens` 上限 8192**:长 JD + 简历 + prompt 容易超,监控 token 数,超了要截断简历或分片
- **`asyncio.run()` 只能用一次**:CLI 里用没问题,web server 里要用 `await` 而不是嵌套 `run`
- **PDF 解析中文乱码**:pdfplumber 对中文一般 ok,但如果 PDF 用了嵌入字体可能出问题,fallback 用 `pypdfium2`
- **网页抓取拿到 JavaScript renderd 空壳**:BOSS 直聘、LinkedIn、拉勾都是 SPA,requests 抓到的是空模板 —— **让用户手动粘贴,不要死磕**

---

## 16. Phase 2 预告(做完 Phase 1 再看)

- FastAPI + 简单 HTML 前端(风格参考 StudyPath AI)
- Chroma 向量库存历史 JD,给"同类岗位匹配"功能
- 简单 memory:记住用户简历版本
- Playwright fallback:处理动态渲染网站
- 中英文双语 README + Demo GIF

---

**最后一句**:Phase 1 的目标是 **Ziming 自己每天在秋招用得起来**。任何拖慢这个目标的功能都推到 Phase 2。**MVP means M-V-P**。
