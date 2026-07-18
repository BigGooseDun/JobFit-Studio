"""配置管理。所有 API key / model 从环境变量读, 不硬编码。"""
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def get_deepseek_model(temperature: float = 0.3, max_tokens: int = 8192) -> ChatOpenAI:
    """返回配置好的 DeepSeek 客户端。

    用 OpenAI-compatible 接口(DeepSeek 官方支持), 而不是专用 SDK。
    trade-off: 专用 SDK 可能有 DeepSeek 独有特性, 但 OpenAI-compatible 接口让"以后换模型
    (OpenAI / 通义 / 本地 vLLM)"只需要改这一个函数, 上层节点代码零改动。对一个要长期维护、
    还要在面试里讲"可扩展性"的项目, 这个解耦更值。

    temperature=0.3: 抽取/分析任务要稳定可复现, 不要发散, 所以偏低。
    max_tokens=8192: DeepSeek 的输出上限。analyze/advise 的结构化输出很大(十几个
      skill_matches 带 evidence + 多条改写建议), 4096 会偶发截断, 导致 with_structured_output
      拿到残缺 JSON 而静默产出 None。顶到上限留足余量。
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY not set. Copy .env.example to .env and fill it."
        )

    # 注意: 绝不 print / log api_key 的任何片段(诚实红线 3.3, 之前泄露过 key)。
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=api_key,
        base_url="https://api.deepseek.com/v1",
        temperature=temperature,
        max_tokens=max_tokens,
    )
