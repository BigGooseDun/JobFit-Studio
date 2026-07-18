"""Node 1: fetch_jd —— 获取 JD 纯文本。

关键决策:
- 不用 LLM, 纯 IO + 简单启发式判断, 快且零成本。判断"是 URL 还是原文"这种事
  用不着模型。
- 分层抓取: httpx 静态优先(快、轻), 失败或正文过短(多半 SPA)才 fallback 到
  Playwright(起浏览器慢且重, 是最后手段)。都失败才让用户手动粘。
- 失败时不 raise, 而是往 state['errors'] 里塞错误信息, 让上层 CLI 决定怎么处理。
  节点内部 raise 会中断整张图, 不利于给用户友好提示。
"""
from jdscout.state import AgentState
from jdscout.tools import web_scraper

# httpx 抓到的正文短于此长度, 视为"静态抓取无效"(SPA 空壳/被挡), 触发 Playwright。
_MIN_STATIC_LEN = 500
# 最终正文短于此长度, 判定为抓取失败。
_MIN_VALID_LEN = 200


async def _fetch_from_url(url: str) -> tuple[str, list[str]]:
    """URL 抓取: httpx 优先, 失败或过短 fallback 到 Playwright。返回 (text, notes)。"""
    notes: list[str] = []

    # 第一层: httpx 静态抓取
    static_text = ""
    try:
        static_text = await web_scraper.fetch_and_extract(url)
        if len(static_text) >= _MIN_STATIC_LEN:
            return static_text, notes
        notes.append(f"static fetch too short ({len(static_text)} chars), trying Playwright")
    except Exception as e:
        notes.append(f"static fetch failed ({e}), trying Playwright")

    # 第二层: Playwright 动态抓取
    try:
        dynamic_text = await web_scraper.fetch_with_playwright(url)
        if len(dynamic_text) >= len(static_text):
            return dynamic_text, notes
        return static_text, notes  # 万一动态反而更差, 保留静态结果
    except Exception as e:
        notes.append(f"Playwright fetch failed ({e})")
        return static_text, notes


async def fetch_jd(state: AgentState) -> dict:
    """获取 JD 纯文本。

    分支:
      1. jd_input 是 URL: httpx -> (不行) Playwright; 仍拿不到足够正文则报错让用户手动粘
      2. jd_input 是纯文本(>= 200 字符): 直接用
    """
    jd_input = state["jd_input"]

    if jd_input.startswith(("http://", "https://")):
        text, notes = await _fetch_from_url(jd_input)
        if len(text) < _MIN_VALID_LEN:
            detail = "; ".join(notes) if notes else "no content"
            return {"errors": [
                f"JD fetch failed ({detail}). This site may be JS-rendered or anti-bot "
                f"protected — please paste the JD text directly."
            ]}
        return {"jd_raw_text": text}

    text = jd_input  # 假设是原文
    if len(text) < _MIN_VALID_LEN:
        return {"errors": ["JD text too short (<200 chars). Provide the full JD."]}
    return {"jd_raw_text": text}
