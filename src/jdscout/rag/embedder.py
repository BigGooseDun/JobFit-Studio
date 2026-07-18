"""本地 embedding(sentence-transformers)。

选型: paraphrase-multilingual-MiniLM-L12-v2
- 免费、无 API 成本(DeepSeek 没官方 embedding API, OpenAI embedding 要额外 key)
- 支持中英文(多语言模型), 本项目 JD 中英混杂
- 模型 ~118MB, 首次用时下载后本地缓存; 单条 embedding ~50ms

模型懒加载(第一次 embed 才加载), 避免 import 就把 torch/模型拉起来拖慢启动。
"""
from typing import Optional

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _model


def embed_text(text: str) -> list[float]:
    """把文本编码成归一化向量(cosine 检索用)。"""
    vec = _get_model().encode(text, normalize_embeddings=True)
    return vec.tolist()


def build_embedding_text(
    role_title: str,
    hard_skills: list[str],
    domain: Optional[str],
    seniority: str,
) -> str:
    """生成用于 embedding 的结构化文本。

    用结构化字段而非 JD 原文: 降噪(去掉薪资/公司套话)、维度可控、可解释。
    检索端和入库端必须用同一个格式, 才能落在同一语义空间。
    """
    return "\n".join([
        role_title,
        "Skills required: " + ", ".join(hard_skills),
        "Domain: " + (domain or "general"),
        "Seniority: " + seniority,
    ])


def build_embedding_text_from_dict(jd: dict) -> str:
    """从 full_result['jd'] 这样的 dict 生成 embedding 文本。"""
    return build_embedding_text(
        role_title=jd.get("role_title", ""),
        hard_skills=jd.get("hard_skills", []) or [],
        domain=jd.get("domain"),
        seniority=jd.get("seniority", "unspecified"),
    )
