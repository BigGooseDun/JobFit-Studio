"""JD summary 生成 —— 拼一句话给历史列表展示用。"""
from jdscout.state import JDRequirements


def generate_summary(jd_structured: JDRequirements) -> str:
    """把结构化 JD 拼成一句话摘要。

    有公司名: "公司 · 岗位 · 地点"; 没有公司名: 兜底成 "岗位 · 薪资"。
    role_title 是必填字段(垃圾输入会被前置的 200 字符保护拦掉), 这里不再兜底。
    """
    if jd_structured.company:
        return f"{jd_structured.company} · {jd_structured.role_title} · {jd_structured.location or '地点未知'}"
    return f"{jd_structured.role_title} · {jd_structured.salary_range or '薪资未知'}"
