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
    """历史记录的 SQLite 存储。首次实例化自动建表(无需手动 migration)。"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
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
            return cur.lastrowid

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
        """删除一条; 返回是否真的删到(id 不存在则 False)。"""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM history_entries WHERE id = ?", (entry_id,))
            return cur.rowcount > 0


# ---- 进程级单例(API 用); 测试可用 set_storage 注入临时库 ----
_storage: Optional[HistoryStorage] = None


def get_storage() -> HistoryStorage:
    global _storage
    if _storage is None:
        _storage = HistoryStorage()
    return _storage


def set_storage(storage: HistoryStorage) -> None:
    global _storage
    _storage = storage
