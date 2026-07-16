"""CLI 入口: python -m jdscout.cli --jd <URL_or_TEXT> --resume <PDF_path>

设计:
- argparse 定义参数; --jd / --resume 必填, --output / --output-md 可选。
- 用 asyncio.run() 把 async 的 graph.ainvoke() 在同步的 main() 里跑起来
  (整个进程只调一次 asyncio.run, 复习 01-notes 概念⑤)。
- 除了机器可读的 JSON, 还能出人类可读的 Markdown 报告(--output-md)。
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

from jdscout.graph import graph
from jdscout.tools.pdf_parser import extract_pdf_text


async def run(jd_input: str, resume_pdf: Path) -> dict:
    """跑完整张图, 返回组装好的报告 dict。"""
    resume_text = extract_pdf_text(resume_pdf)
    initial_state = {
        "jd_input": jd_input,
        "resume_raw_text": resume_text,
    }
    final_state = await graph.ainvoke(initial_state)

    return {
        "jd": final_state["jd_structured"].model_dump() if final_state.get("jd_structured") else None,
        "gap": final_state["gap_analysis"].model_dump() if final_state.get("gap_analysis") else None,
        "advice": final_state["advice"].model_dump() if final_state.get("advice") else None,
        "errors": final_state.get("errors", []),
    }


def render_markdown(report: dict) -> str:
    """把报告 dict 渲染成人类可读的 Markdown。"""
    jd = report.get("jd")
    gap = report.get("gap")
    advice = report.get("advice")
    lines: list[str] = []

    if jd:
        title = jd.get("role_title", "?")
        company = jd.get("company") or "未知公司"
        lines += [f"# JD-Scout 报告 — {title} @ {company}", ""]
    else:
        lines += ["# JD-Scout 报告", ""]

    if report.get("errors"):
        lines += ["## ⚠️ 运行错误", ""]
        lines += [f"- {e}" for e in report["errors"]]
        lines += [""]

    if jd:
        lines += ["## 岗位需求", ""]
        if jd.get("location"):
            lines.append(f"- **地点**: {jd['location']}")
        if jd.get("seniority"):
            lines.append(f"- **资历**: {jd['seniority']}")
        if jd.get("salary_range"):
            lines.append(f"- **薪资**: {jd['salary_range']}")
        if jd.get("hard_skills"):
            lines.append(f"- **硬技能**: {', '.join(jd['hard_skills'])}")
        if jd.get("nice_to_have"):
            lines.append(f"- **加分项**: {', '.join(jd['nice_to_have'])}")
        lines.append("")

    if gap:
        lines += ["## 匹配度分析", "", f"**总体匹配度: {gap.get('overall_match_score')}/100**", ""]
        if gap.get("skill_matches"):
            lines += ["| 技能 | 状态 | 证据 |", "| --- | --- | --- |"]
            for sm in gap["skill_matches"]:
                ev = (sm.get("evidence") or "").replace("|", "\\|").replace("\n", " ")
                lines.append(f"| {sm['skill']} | {sm['status']} | {ev} |")
            lines.append("")
        if gap.get("strengths"):
            lines += ["### 强项", ""] + [f"- {s}" for s in gap["strengths"]] + [""]
        if gap.get("critical_gaps"):
            lines += ["### 关键缺口", ""] + [f"- {g}" for g in gap["critical_gaps"]] + [""]

    if advice:
        lines += ["## 建议", "", f"**是否投递: {advice.get('should_apply')}**", ""]
        if advice.get("should_apply_reason"):
            lines += [advice["should_apply_reason"], ""]
        if advice.get("bullet_rewrites"):
            lines += ["### 简历改写建议", ""]
            for i, br in enumerate(advice["bullet_rewrites"], 1):
                lines += [
                    f"**{i}. 原文**: {br['original']}",
                    f"   - **改写**: {br['rewritten']}",
                    f"   - **理由**: {br['rationale']}",
                    "",
                ]
        if advice.get("interview_prep_focus"):
            lines += ["### 面试准备重点", ""] + [f"- {x}" for x in advice["interview_prep_focus"]] + [""]
        if advice.get("questions_to_ask_interviewer"):
            lines += ["### 反问面试官", ""] + [f"- {q}" for q in advice["questions_to_ask_interviewer"]] + [""]

    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jdscout",
        description="JD-Scout: 把一份岗位 JD 和你的简历做深度对比, 输出匹配度、改写建议和面试重点。",
        epilog=(
            "示例:\n"
            "  # JD 用原文, 报告打印到终端\n"
            '  uv run python -m jdscout.cli --jd "岗位职责: ..." --resume examples/sample_resume.pdf\n\n'
            "  # JD 用 URL, 同时存 JSON 和 Markdown\n"
            '  uv run python -m jdscout.cli --jd "https://jobs.example.com/123" \\\n'
            "      --resume ./my_resume.pdf --output report.json --output-md report.md\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--jd", required=True, help="JD 的 URL 或直接粘贴的原文")
    parser.add_argument("--resume", required=True, type=Path, help="简历 PDF 路径")
    parser.add_argument("--output", type=Path, help="把 JSON 报告存到此路径")
    parser.add_argument("--output-md", type=Path, help="把 Markdown 报告存到此路径")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.resume.exists():
        parser.error(f"简历 PDF 不存在: {args.resume}")

    report = asyncio.run(run(args.jd, args.resume))

    json_str = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(json_str, encoding="utf-8")
        print(f"JSON 报告已保存到 {args.output}")
    if args.output_md:
        args.output_md.write_text(render_markdown(report), encoding="utf-8")
        print(f"Markdown 报告已保存到 {args.output_md}")
    if not args.output and not args.output_md:
        print(json_str)

    # 有错误时以非零退出码结束, 方便脚本/CI 判断成败
    return 1 if report.get("errors") else 0


if __name__ == "__main__":
    sys.exit(main())
