"""检索 top-k 相似历史投递。"""
from typing import Callable, Optional

from jdscout.state import JDRequirements, SimilarHistory
from jdscout.rag.embedder import embed_text, build_embedding_text
from jdscout.rag.vector_store import VectorStore, get_vector_store

# 只保留 cosine 相似度 > 阈值的结果, 过滤弱相关(见 notes)。
_SIMILARITY_THRESHOLD = 0.65


def find_similar(
    jd_structured: JDRequirements,
    top_k: int = 3,
    exclude_id: Optional[int] = None,
    threshold: float = _SIMILARITY_THRESHOLD,
    store: Optional[VectorStore] = None,
    embedder: Callable[[str], list[float]] = embed_text,
) -> list[SimilarHistory]:
    """检索与当前 JD 最相似的历史投递。

    - 用和入库端相同的结构化文本格式生成 query 向量。
    - 只返回相似度 > threshold 的(弱相关不进 prompt)。
    - exclude_id: 若当前这条已在库里, 排除自己。
    """
    store = store or get_vector_store()
    if store.count() == 0:
        return []

    query_text = build_embedding_text(
        role_title=jd_structured.role_title,
        hard_skills=jd_structured.hard_skills,
        domain=jd_structured.domain,
        seniority=jd_structured.seniority,
    )
    # 多取一个, 给"排除自己"留余量
    n = top_k + 1 if exclude_id is not None else top_k
    res = store.query(embedder(query_text), top_k=n)

    ids = res.get("ids", [[]])[0]
    dists = res.get("distances", [[]])[0]
    metas = res.get("metadatas", [[]])[0]

    out: list[SimilarHistory] = []
    for id_, dist, meta in zip(ids, dists, metas):
        hid = int(id_)
        if exclude_id is not None and hid == exclude_id:
            continue
        similarity = 1.0 - float(dist)   # cosine 距离 -> 相似度
        if similarity < threshold:
            continue
        score = meta.get("match_score")
        out.append(
            SimilarHistory(
                history_id=hid,
                jd_summary=meta.get("jd_summary", ""),
                match_score=None if score in (None, -1) else int(score),
                should_apply=meta.get("should_apply") or None,
                similarity_score=round(similarity, 3),
                created_at=meta.get("created_at", ""),
            )
        )
        if len(out) >= top_k:
            break
    return out


def format_similar_histories_for_prompt(similar: list[SimilarHistory]) -> str:
    """把检索结果拼成注入 advise prompt 的文本。"""
    if not similar:
        return "(This is the user's first application in this domain; no historical context available.)"
    lines = []
    for i, s in enumerate(similar, 1):
        score = s.match_score if s.match_score is not None else "?"
        lines.append(
            f"{i}. {s.jd_summary} — match_score={score}, should_apply={s.should_apply or '?'}, "
            f"similarity={int(s.similarity_score * 100)}%, applied {s.created_at}"
        )
    return "\n".join(lines)
