"""API 层的请求/响应 schema。

为什么和 state.py 分开:
- state.py 的 Pydantic model 是"内部工作流的数据契约"(节点之间、给 LLM 用)。
- 这里的 schema 是"对外 HTTP 接口的契约"(前端/curl 用)。
两者会演化出不同的关注点:对外接口要考虑版本兼容、字段裁剪、错误包装, 而内部 model 只服务
工作流。分开后, 改内部结构不会意外破坏 API 契约, 反之亦然。响应里复用内部 model 作为嵌套
字段是可以的(它们本就是要透出的数据), 但"顶层信封"归 API 层own。
"""
from typing import Optional

from pydantic import BaseModel, Field

from jdscout.state import JDRequirements, GapAnalysis, ResumeAdvice


class AnalyzeResponse(BaseModel):
    """POST /api/analyze 的响应, 形状与 CLI 的 sample_output.json 一致。"""
    jd: Optional[JDRequirements] = Field(default=None, description="结构化 JD 需求, 提取失败则 null")
    gap: Optional[GapAnalysis] = Field(default=None, description="简历 gap 分析, 未产出则 null")
    advice: Optional[ResumeAdvice] = Field(default=None, description="改写建议 + 面试重点, 未产出则 null")
    errors: list[str] = Field(default_factory=list, description="各节点累积的错误信息")
    history_id: Optional[int] = Field(default=None, description="本次分析存档的历史记录 id(未存档则 null)")


class HistoryListItem(BaseModel):
    """GET /api/history 列表项(不含 full_result, 减少体积)。"""
    id: int
    created_at: str
    jd_summary: str
    match_score: Optional[int] = None
    should_apply: Optional[str] = None


class HistoryDetail(BaseModel):
    """GET /api/history/:id 单条完整记录。"""
    id: int
    created_at: str
    jd_text: str
    jd_summary: str
    resume_filename: str
    match_score: Optional[int] = None
    should_apply: Optional[str] = None
    full_result: dict


class ErrorResponse(BaseModel):
    """统一错误信封: 业务错误 400 / 系统错误 500 都用这个形状。"""
    type: str = Field(description="错误类型, 如 'invalid_file' / 'pdf_parse_error' / 'internal_error'")
    message: str = Field(description="人类可读的错误说明")
