"""PDF 简历解析工具。

选型 trade-off:
- 主用 pdfplumber, 不用 pypdf: pypdf 对多列排版会把两列文字按物理行混行(左栏一句 +
  右栏一句拼成一行), 语义全乱; pdfplumber 按坐标聚类, 保序更可靠。简历偶有双栏, 值这个依赖。
- fallback 用 pypdfium2, 不用 LandingAI 之类付费 API: MVP 不引入外部收费依赖。
  pypdfium2 是 pdfplumber 的依赖链已经带进来的(白得), 且底层是 Google 的 PDFium 引擎。

为什么需要 fallback(真实踩到的坑):
  有些 PDF(比如 Markdown 导出的简历)用"重复描边"的方式模拟粗体, pdfplumber 会把每个
  粗体字形抽取两遍 —— "Technical Skills" 变成 "TTeecchhnniiccaall SSkkiillllss"。
  这种双写会污染喂给 LLM 的简历文本。检测手段: 统计"连续重复字符"的比例, 正常英文文本
  约 3-4%, 双写会飙到 13%+。超过阈值就用 pypdfium2 重抽(实测它对同一文件是 1.8%, 干净)。

MVP 限制:
- 只支持文字版 PDF, 不支持扫描版(需要 OCR, Phase 2 再加)。
- 假设单列排版, 双列/图片版可能失败(降级方案: 让用户改成 docx→单列 pdf)。
"""
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium

# 连续重复字符比例超过这个值, 判定为"粗体双写"污染, 触发 fallback。
# 正常英文 ~3-4%, 中文更低; 双写案例实测 13.5%, 8% 能干净分开两者。
_DUP_RATIO_THRESHOLD = 0.08


def _consecutive_dup_ratio(text: str) -> float:
    """非空白字符里, 与前一个字符相同的比例。用来嗅探"粗体双写"污染。"""
    chars = [c for c in text if not c.isspace()]
    if len(chars) < 2:
        return 0.0
    dup = sum(1 for i in range(1, len(chars)) if chars[i] == chars[i - 1])
    return dup / len(chars)


def _extract_with_pdfplumber(pdf_path: Path) -> str:
    texts: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            texts.append(page_text.strip())
    return "\n\n".join(t for t in texts if t)


def _extract_with_pypdfium2(pdf_path: Path) -> str:
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        parts = [page.get_textpage().get_text_range() for page in pdf]
    finally:
        pdf.close()
    return "\n\n".join(p.strip() for p in parts if p.strip())


def extract_pdf_text(pdf_path: Path) -> str:
    """提取 PDF 全文, 页与页之间用空行分隔。

    主用 pdfplumber; 若检测到粗体双写污染, 自动 fallback 到 pypdfium2。
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Resume PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected .pdf file, got {pdf_path.suffix}")

    text = _extract_with_pdfplumber(pdf_path)

    if _consecutive_dup_ratio(text) > _DUP_RATIO_THRESHOLD:
        # pdfplumber 抽到了双写污染, 换 pypdfium2 重抽
        fallback = _extract_with_pypdfium2(pdf_path)
        # 只有当 fallback 确实更干净时才采用(防止个别文件 pypdfium2 反而更差)
        if _consecutive_dup_ratio(fallback) < _consecutive_dup_ratio(text):
            return fallback

    return text
