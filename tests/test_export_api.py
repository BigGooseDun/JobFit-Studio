from fastapi.testclient import TestClient

from jdscout.api.server import app


def test_export_endpoint_returns_docx():
    client = TestClient(app)
    with open("examples/sample_resume.pdf", "rb") as resume:
        response = client.post(
            "/api/resume/export",
            data={
                "output_format": "docx",
                "rewrites_json": "[{\"original\": \"Python\", \"rewritten\": \"Python and FastAPI\"}]",
            },
            files={"resume_file": ("resume.pdf", resume, "application/pdf")},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert response.content[:2] == b"PK"


def test_export_endpoint_returns_pdf():
    client = TestClient(app)
    with open("examples/sample_resume.pdf", "rb") as resume:
        response = client.post(
            "/api/resume/export",
            data={
                "output_format": "pdf",
                "rewrites_json": "[{\"original\": \"Python\", \"rewritten\": \"Python and FastAPI\"}]",
            },
            files={"resume_file": ("resume.pdf", resume, "application/pdf")},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")


def test_export_endpoint_keeps_unmatched_rewrite_in_generated_document():
    client = TestClient(app)
    with open("examples/sample_resume.pdf", "rb") as resume:
        response = client.post(
            "/api/resume/export",
            data={
                "output_format": "docx",
                "match_score": "42",
                "rewrites_json": "[{\"original\": \"这段原文不存在\", \"rewritten\": \"负责推动项目落地并持续优化交付流程\"}]",
            },
            files={"resume_file": ("resume.pdf", resume, "application/pdf")},
        )

    assert response.status_code == 200
    assert response.headers["X-Resume-Rewrites-Applied"] == "0"
    assert response.headers["X-Resume-Rewrites-Pending"] == "1"
    assert response.content[:2] == b"PK"


def test_export_endpoint_rejects_unknown_format():
    client = TestClient(app)
    with open("examples/sample_resume.pdf", "rb") as resume:
        response = client.post(
            "/api/resume/export",
            data={"output_format": "txt", "rewrites_json": "[]"},
            files={"resume_file": ("resume.pdf", resume, "application/pdf")},
        )
    assert response.status_code == 400
    assert response.json()["detail"]["type"] == "invalid_format"
