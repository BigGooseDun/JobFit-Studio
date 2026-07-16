# JD-Scout（好想上岸）

一个用 LangGraph 做的 AI Agent，帮求职者把每一份岗位 JD 看穿看透：自动抓取 JD → 结构化提取需求 → 与用户简历做 gap 分析 → 生成简历改写建议和面试重点。

## 快速开始

```bash
# 1. 安装依赖（用 uv）
uv sync --extra dev

# 2. 配置 API key
cp .env.example .env      # 然后填入你的 DEEPSEEK_API_KEY

# 3. 跑一次分析：JD 原文（或 URL） + 简历 PDF
uv run python -m jdscout.cli \
    --jd "把 JD 全文粘贴到这里，或直接给一个 URL" \
    --resume examples/sample_resume.pdf \
    --output report.json --output-md report.md
```

不加 `--output` 时报告直接打印到终端。查看全部参数：`uv run python -m jdscout.cli --help`。

一份真实输出示例见 [`examples/sample_output.json`](examples/sample_output.json) / [`examples/sample_output.md`](examples/sample_output.md)。

## 工作流

```
START → fetch_jd → extract → analyze → advise → END
```

| 节点 | 作用 | 产出 |
| --- | --- | --- |
| `fetch_jd` | 抓取/接收 JD 文本（纯 IO，无 LLM） | `jd_raw_text` |
| `extract` | 结构化提取岗位需求（Pydantic 强约束） | `JDRequirements` |
| `analyze` | 简历 vs JD 差距分析 | `GapAnalysis` |
| `advise` | 简历改写建议 + 面试重点 | `ResumeAdvice` |

## 已知限制（MVP）

- 动态渲染的招聘网站（BOSS 直聘 / LinkedIn 等）抓不到，请手动粘贴 JD 文本。
- 只支持文字版 PDF 简历，扫描版需要 OCR（Phase 2）。
