"""State 与结构化输出 schema 定义。

设计分工（重要）:
- AgentState 用 TypedDict: 它是节点之间传递的"数据黑板", 每个节点只部分更新,
  运行时就是普通 dict, 轻量、灵活。
- LLM 产出的字段(JDRequirements / GapAnalysis / ResumeAdvice)用 Pydantic BaseModel:
  需要运行时强校验(反幻觉), .with_structured_output() 也依赖 Pydantic schema。
"""
from typing import Optional, Annotated
from operator import add

from typing_extensions import TypedDict
from pydantic import BaseModel, Field


# ---------- Pydantic Schemas (LLM 结构化输出必须符合) ----------

class JDRequirements(BaseModel):
    """从 JD 抽取的结构化需求。"""
    role_title: str = Field(description="岗位名称,例如 'AI Agent 后端工程师'")
    company: Optional[str] = Field(default=None, description="公司名称,如未提及则 null")
    location: Optional[str] = Field(default=None, description="工作地点")
    seniority: str = Field(
        description="资历要求: 'intern' / 'junior' / 'mid' / 'senior' / 'unspecified'"
    )

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
        default=None, description="经验年限要求, 例如 '1-3年' / '3-5年' / '应届'"
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
    """单个技能的匹配情况。"""
    skill: str
    status: str = Field(description="'matched' / 'partial' / 'missing'")
    evidence: Optional[str] = Field(
        default=None,
        description="如果 matched, 引用简历里的哪句话作为证据"
    )


class GapAnalysis(BaseModel):
    """简历 vs JD 的差距分析。"""
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
    """针对简历某条 bullet 的改写建议。"""
    original: str = Field(description="简历原文摘录 (不改动)")
    rewritten: str = Field(description="改写后的版本")
    rationale: str = Field(description="为什么这样改, 1-2 句话")


class ResumeAdvice(BaseModel):
    """给用户的最终建议。"""
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
    """整个工作流共享的 state。

    total=False: 初始 State 允许只填部分字段(如只给 jd_input/resume_raw_text),
    其余字段由各节点跑完后逐步填上。
    """
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
    # 用 Annotated[..., add] 声明 reducer: 多个节点各自 append error 时自动"列表拼接"
    # 而不是"后者覆盖前者"。蓝图第 2 节原文写的是裸 list[str], 那样在有多个节点都可能
    # 写 errors 的场景下(fetch_jd 失败 + extract 又失败)会丢掉前一个错误 —— 这里提前
    # 用 reducer 修正, 对应 01-hello-graph/notes.md 概念①。
    errors: Annotated[list[str], add]
