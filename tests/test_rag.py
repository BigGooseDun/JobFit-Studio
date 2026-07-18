"""RAG 单元测试。用 2 维假向量, 不加载 sentence-transformers(torch), 只测存/检索/阈值逻辑。"""
import pytest

from jdscout.rag.vector_store import VectorStore
from jdscout.rag.retriever import find_similar
from jdscout.state import JDRequirements


def _meta(hid, summary="岗位", score=80, apply="worth_trying"):
    return {
        "history_id": hid, "jd_summary": summary, "match_score": score,
        "should_apply": apply, "created_at": "2026-07-17T10:00:00",
    }


@pytest.fixture
def store(tmp_path):
    return VectorStore(persist_dir=tmp_path / "chroma")


def _jd() -> JDRequirements:
    return JDRequirements(
        role_title="AI Agent 工程师", seniority="mid",
        hard_skills=["Python", "LangGraph"], key_responsibilities=["搭 Agent"],
    )


def test_add_query_delete(store):
    store.add("1", "docA", _meta(1, "A公司"), [1.0, 0.0])
    store.add("2", "docB", _meta(2, "B公司"), [0.0, 1.0])
    assert store.count() == 2

    res = store.query([1.0, 0.0], top_k=2)
    assert res["ids"][0][0] == "1"          # 最近的是 A(相同向量)
    assert set(store.existing_ids()) == {"1", "2"}

    store.delete("2")
    assert store.count() == 1
    assert store.existing_ids() == {"1"}


def test_retriever_threshold_filters_weak_matches(store):
    # A 与 query 完全同向(sim=1.0), B 正交(sim=0.0, 应被 0.65 阈值过滤)
    store.add("1", "docA", _meta(1, "A公司 · AI Agent"), [1.0, 0.0])
    store.add("2", "docB", _meta(2, "B公司 · 前端"), [0.0, 1.0])

    fake_embedder = lambda text: [1.0, 0.0]
    out = find_similar(_jd(), top_k=3, store=store, embedder=fake_embedder)

    assert len(out) == 1                     # 只有 A 过阈值
    assert out[0].history_id == 1
    assert out[0].similarity_score > 0.65
    assert out[0].jd_summary == "A公司 · AI Agent"


def test_retriever_excludes_self(store):
    store.add("1", "docA", _meta(1), [1.0, 0.0])
    store.add("2", "docB", _meta(2), [0.0, 1.0])
    fake_embedder = lambda text: [1.0, 0.0]

    # 排除 id=1 后, 仅剩的 id=2 又因相似度不足被过滤 -> 空
    out = find_similar(_jd(), top_k=3, exclude_id=1, store=store, embedder=fake_embedder)
    assert out == []


def test_retriever_empty_store_returns_empty(store):
    out = find_similar(_jd(), store=store, embedder=lambda t: [1.0, 0.0])
    assert out == []
