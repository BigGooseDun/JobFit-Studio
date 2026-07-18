"""History 领域模型。"""
from typing import Optional

from pydantic import BaseModel, Field


class HistoryEntry(BaseModel):
    """一条历史分析记录。

    对应 SQLite 表 history_entries。full_result 在存储层与 full_result_json(TEXT)
    之间做 dict<->json 转换; 列表查询时不加载它(留空 dict), 详情查询才填。
    """
    id: Optional[int] = None
    created_at: str                      # ISO 8601
    jd_text: str                         # JD 原文, 方便重新分析
    jd_summary: str                      # 拼出来的一句话, 列表展示用
    resume_filename: str                 # 只存文件名, 不存 PDF 内容(隐私)
    match_score: Optional[int] = None    # 0-100
    should_apply: Optional[str] = None
    full_result: dict = Field(default_factory=dict)   # 完整分析结果
