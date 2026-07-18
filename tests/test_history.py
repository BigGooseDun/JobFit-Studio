"""HistoryStorage 单元测试(用临时 SQLite 文件, 不碰真实 ~/.jdscout)。"""
import pytest

from jdscout.history.models import HistoryEntry
from jdscout.history.storage import HistoryStorage
from jdscout.history.summary import generate_summary
from jdscout.state import JDRequirements


@pytest.fixture
def storage(tmp_path):
    return HistoryStorage(db_path=tmp_path / "history.db")


def _entry(summary="某公司 · AI Agent · 深圳", score=82, apply="strongly_recommend") -> HistoryEntry:
    return HistoryEntry(
        created_at="2026-07-17T10:00:00",
        jd_text="一段足够长的 JD 原文……",
        jd_summary=summary,
        resume_filename="resume.pdf",
        match_score=score,
        should_apply=apply,
        full_result={"gap": {"overall_match_score": score}, "advice": {"should_apply": apply}},
    )


def test_create_and_get(storage):
    new_id = storage.create_entry(_entry())
    assert isinstance(new_id, int)

    got = storage.get_entry(new_id)
    assert got is not None
    assert got.id == new_id
    assert got.match_score == 82
    assert got.should_apply == "strongly_recommend"
    # full_result 在详情里应完整还原
    assert got.full_result["gap"]["overall_match_score"] == 82


def test_list_orders_desc_and_omits_full_result(storage):
    id1 = storage.create_entry(_entry(summary="A公司", score=60))
    id2 = storage.create_entry(_entry(summary="B公司", score=90))
    # 让第二条 created_at 更新, 保证倒序稳定
    with storage._connect() as conn:
        conn.execute("UPDATE history_entries SET created_at=? WHERE id=?", ("2026-07-17T12:00:00", id2))

    entries = storage.list_entries()
    assert [e.id for e in entries] == [id2, id1]         # 倒序
    assert all(e.full_result == {} for e in entries)     # 列表不带 full_result


def test_get_missing_returns_none(storage):
    assert storage.get_entry(9999) is None


def test_delete(storage):
    new_id = storage.create_entry(_entry())
    assert storage.delete_entry(new_id) is True
    assert storage.get_entry(new_id) is None
    # 再删同一个 id 返回 False
    assert storage.delete_entry(new_id) is False


def test_summary_with_company():
    jd = JDRequirements(
        role_title="AI Agent 工程师", company="某公司", location="深圳",
        seniority="mid", hard_skills=["Python"], key_responsibilities=["搭 Agent"],
    )
    assert generate_summary(jd) == "某公司 · AI Agent 工程师 · 深圳"


def test_summary_without_company():
    jd = JDRequirements(
        role_title="后端工程师", company=None, salary_range="20-35K",
        seniority="mid", hard_skills=["Python"], key_responsibilities=["写后端"],
    )
    assert generate_summary(jd) == "后端工程师 · 20-35K"
