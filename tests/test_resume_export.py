import pytest
from docx import Document
from io import BytesIO
from reportlab.pdfgen.canvas import Canvas
from PIL import Image

from jdscout.tools.resume_export import (
    Rewrite,
    apply_rewrites,
    apply_rewrites_with_report,
    parse_rewrites,
    render_pdf,
    render_docx,
    _lines,
    _section_groups,
    _is_bullet,
    _clean_bullet,
)
from jdscout.tools.pdf_parser import extract_resume_photo


def test_apply_rewrites_preserves_unselected_text():
    text = "张三\n工作经历\n- 使用 Python 完成服务开发\n- 负责测试和部署"
    out = apply_rewrites(text, [Rewrite("使用 Python 完成服务开发", "使用 Python 和 FastAPI 完成服务开发")])
    assert "使用 Python 和 FastAPI 完成服务开发" in out
    assert "负责测试和部署" in out


def test_apply_rewrites_keeps_missing_source_for_export_fallback():
    report = apply_rewrites_with_report(
        "张三\n工作经历", [Rewrite("不存在的经历", "新的经历")]
    )
    assert report.text == "张三\n工作经历"
    assert report.pending == (Rewrite("不存在的经历", "新的经历"),)
    assert apply_rewrites("张三\n工作经历", [Rewrite("不存在的经历", "新的经历")]) == "张三\n工作经历"


def test_apply_rewrites_normalizes_chinese_line_breaks_and_punctuation():
    text = "张三\n项目经历\n提出一种降噪算法，有效抑制井场内的周期性\n噪声和随机噪声。"
    report = apply_rewrites_with_report(
        text,
        [Rewrite("提出一种降噪算法，有效抑制井场内的周期性噪声和随机噪声。", "提出并实现降噪算法，提升识别精度。")],
    )
    assert report.pending == ()
    assert "提出并实现降噪算法，提升识别精度。" in report.text


def test_render_docx_appends_pending_rewrites_for_low_score():
    payload = render_docx(
        "张三\n项目经历\n- 已完成项目开发",
        [Rewrite("无法定位的原文", "负责梳理需求并推进项目交付。")],
        match_score=42,
    )
    document = Document(BytesIO(payload))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "低匹配度简历的润色备选" in text
    assert "负责梳理需求并推进项目交付。" in text


def test_extract_resume_photo_renders_embedded_portrait(tmp_path):
    image_path = tmp_path / "photo.jpg"
    pdf_path = tmp_path / "resume.pdf"
    Image.new("RGB", (100, 120), "red").save(image_path)
    canvas = Canvas(str(pdf_path))
    canvas.drawImage(str(image_path), 50, 650, 50, 60)
    canvas.drawString(50, 600, "张三")
    canvas.save()

    photo = extract_resume_photo(pdf_path)
    assert photo and photo[:2] == b"\xff\xd8"


def test_parse_rewrites_validates_payload():
    assert parse_rewrites([{"original": "a", "rewritten": "b"}]) == [Rewrite("a", "b")]
    with pytest.raises(ValueError):
        parse_rewrites([{"original": "", "rewritten": "b"}])


def test_render_pdf_produces_pdf_bytes():
    payload = render_pdf("张三\n工作经历\n- 使用 Python 完成服务开发", [Rewrite("使用 Python", "使用 Python 和 FastAPI")])
    assert payload.startswith(b"%PDF")


def test_pdf_text_cleanup_removes_cid_artifacts_and_orphan_bullets():
    assert _lines("张三\n•\n(cid:127) 项目经历\n\ufffd有效成果") == ["张三", "项目经历", "有效成果"]
    assert _is_bullet("□研究背景：项目内容")
    assert _clean_bullet("□研究背景：项目内容") == "研究背景：项目内容"


def test_sections_are_split_for_natural_pagination():
    groups = _section_groups(["项目经历", "项目一", "项目二", "荣誉与证书", "证书一"])
    assert groups == [["项目经历", "项目一", "项目二"], ["荣誉与证书", "证书一"]]


def test_render_docx_produces_zip_bytes():
    pytest.importorskip("docx")
    payload = render_docx("张三\n工作经历\n- 使用 Python 完成服务开发", [])
    assert payload[:2] == b"PK"
