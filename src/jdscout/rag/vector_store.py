"""Chroma 向量库封装。

位置: ~/.jdscout/chroma/(和 SQLite 同目录, 一起走 volume 持久化)。
Collection: "jd_history", cosine 距离空间。

底层方法(add/query/delete/count)只收/发 embedding 向量, 不碰 embedder ——
方便测试用假向量、也让"存什么向量"的策略集中在 index_entry 一处。
"""
import os
from pathlib import Path
from typing import Optional

from jdscout.history.models import HistoryEntry
from jdscout.rag.embedder import embed_text, build_embedding_text_from_dict

_COLLECTION = "jd_history"


def _default_dir() -> Path:
    # 可用 CHROMA_DIR 覆盖(见 README Configuration), 默认 ~/.jdscout/chroma。
    env = os.getenv("CHROMA_DIR")
    return Path(env) if env else Path.home() / ".jdscout" / "chroma"


class VectorStore:
    def __init__(self, persist_dir: Optional[Path] = None):
        self.persist_dir = Path(persist_dir) if persist_dir else _default_dir()
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._collection = None

    def _coll(self):
        if self._collection is None:
            import chromadb
            client = chromadb.PersistentClient(path=str(self.persist_dir))
            self._collection = client.get_or_create_collection(
                name=_COLLECTION, metadata={"hnsw:space": "cosine"}
            )
        return self._collection

    # ---- 低层: 直接收发向量(测试可传假向量) ----
    def add(self, id: str, document: str, metadata: dict, embedding: list[float]) -> None:
        self._coll().upsert(
            ids=[str(id)], documents=[document], metadatas=[metadata], embeddings=[embedding]
        )

    def query(self, embedding: list[float], top_k: int) -> dict:
        return self._coll().query(query_embeddings=[embedding], n_results=top_k)

    def delete(self, id: str) -> None:
        self._coll().delete(ids=[str(id)])

    def count(self) -> int:
        return self._coll().count()

    def existing_ids(self) -> set[str]:
        return set(self._coll().get()["ids"])

    # ---- 高层: 从 HistoryEntry 生成向量并入库 ----
    def index_entry(self, entry: HistoryEntry) -> None:
        """给一条历史记录生成 embedding 并写入(需要 full_result['jd'])。"""
        jd = (entry.full_result or {}).get("jd")
        if not jd or entry.id is None:
            return
        text = build_embedding_text_from_dict(jd)
        self.add(
            id=str(entry.id),
            document=text,
            metadata={
                "history_id": entry.id,
                "jd_summary": entry.jd_summary,
                "match_score": entry.match_score if entry.match_score is not None else -1,
                "should_apply": entry.should_apply or "",
                "created_at": entry.created_at,
            },
            embedding=embed_text(text),
        )

    def remove(self, history_id: int) -> None:
        self.delete(str(history_id))


# ---- 进程级单例 ----
_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


def set_vector_store(store: Optional[VectorStore]) -> None:
    global _store
    _store = store
