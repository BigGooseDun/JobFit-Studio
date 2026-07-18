"""SQLite 存储层。

用 Python 自带的 sqlite3, 不引 SQLAlchemy —— 单用户、零配置、嵌入式, ORM 是杀鸡用牛刀。
DB 文件默认放 ~/.jdscout/history.db(用户数据, 不进 git 也不进 Docker 镜像)。
"""
import json
import sqlite3
from pathlib import Path
from typing import Optional

from jdscout.history.models import HistoryEntry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS history_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    jd_text TEXT NOT NULL,
    jd_summary TEXT NOT NULL,
    resume_filename TEXT NOT NULL,
    match_score INTEGER,
    should_apply TEXT,
    full_result_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_created_at ON history_entries(created_at DESC);
"""


def _default_db_path() -> Path:
    return Path.home() / ".jdscout" / "history.db"


class HistoryStorage:
    """历史记录的 SQLite 存储。首次实例化自动建表(无需手动 migration)。

    vector_store: 可选的向量库。传入时, create/delete 会同步写/删向量; 不传(如单元测试)
    则纯 SQLite, 不触发 embedding/Chroma(保持测试轻量、离线)。
    """

    def __init__(self, db_path: Optional[Path] = None, vector_store=None):
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.vector_store = vector_store
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row   # 让查询结果能按列名取
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def create_entry(self, entry: HistoryEntry) -> int:
        """插入一条记录, 返回自增 id。"""
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO history_entries
                   (created_at, jd_text, jd_summary, resume_filename,
                    match_score, should_apply, full_result_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.created_at,
                    entry.jd_text,
                    entry.jd_summary,
                    entry.resume_filename,
                    entry.match_score,
                    entry.should_apply,
                    json.dumps(entry.full_result, ensure_ascii=False),
                ),
            )
            new_id = cur.lastrowid

        # 先写 SQLite(拿到自增 id)再写向量库, 顺序重要: Chroma 的 id 用 SQLite 的 id。
        if self.vector_store is not None:
            entry.id = new_id
            try:
                self.vector_store.index_entry(entry)
            except Exception:
                # 向量化失败不该让"存历史"整体失败(SQLite 已写成功)。
                pass
        return new_id

    def list_entries(self, limit: int = 50) -> list[HistoryEntry]:
        """列表, 按 created_at 倒序。不加载 full_result_json(列表不需要, 省体积)。"""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT id, created_at, jd_text, jd_summary, resume_filename,
                          match_score, should_apply
                   FROM history_entries
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [
            HistoryEntry(
                id=r["id"],
                created_at=r["created_at"],
                jd_text=r["jd_text"],
                jd_summary=r["jd_summary"],
                resume_filename=r["resume_filename"],
                match_score=r["match_score"],
                should_apply=r["should_apply"],
                full_result={},   # 列表不带完整结果
            )
            for r in rows
        ]

    def get_entry(self, entry_id: int) -> Optional[HistoryEntry]:
        """按 id 取单条完整记录; 不存在返回 None。"""
        with self._connect() as conn:
            r = conn.execute(
                "SELECT * FROM history_entries WHERE id = ?", (entry_id,)
            ).fetchone()
        if r is None:
            return None
        return HistoryEntry(
            id=r["id"],
            created_at=r["created_at"],
            jd_text=r["jd_text"],
            jd_summary=r["jd_summary"],
            resume_filename=r["resume_filename"],
            match_score=r["match_score"],
            should_apply=r["should_apply"],
            full_result=json.loads(r["full_result_json"]),
        )

    def delete_entry(self, entry_id: int) -> bool:
        """删除一条; 返回是否真的删到(id 不存在则 False)。同步删向量, 防止"僵尸检索"。"""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM history_entries WHERE id = ?", (entry_id,))
            deleted = cur.rowcount > 0
        if deleted and self.vector_store is not None:
            try:
                self.vector_store.remove(entry_id)
            except Exception:
                pass
        return deleted


# ---- 进程级单例(API 用); 测试可用 set_storage 注入临时库 ----
_storage: Optional[HistoryStorage] = None


def get_storage() -> HistoryStorage:
    global _storage
    if _storage is None:
        # 默认存储挂上向量库, 让 create/delete 同步维护 Chroma。
        from jdscout.rag.vector_store import get_vector_store
        _storage = HistoryStorage(vector_store=get_vector_store())
    return _storage


def set_storage(storage: HistoryStorage) -> None:
    global _storage
    _storage = storage


def reindex_missing(storage: HistoryStorage) -> int:
    """平滑升级: 给 SQLite 里有、但向量库里没有的历史补索引。返回补了多少条。

    场景: M8 之前存的历史(那时还没向量库), 或手动删了 ~/.jdscout/chroma/ 后重启。
    """
    if storage.vector_store is None:
        return 0
    existing = storage.vector_store.existing_ids()
    count = 0
    for item in storage.list_entries(limit=10_000):
        if str(item.id) in existing:
            continue
        full = storage.get_entry(item.id)   # 需要 full_result 才能生成 embedding
        if full is None:
            continue
        storage.vector_store.index_entry(full)
        count += 1
    return count
