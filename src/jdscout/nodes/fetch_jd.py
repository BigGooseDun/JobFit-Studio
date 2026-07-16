"""Node 1: fetch_jd —— 获取 JD 纯文本。

关键决策:
- 不用 LLM, 纯 IO + 简单启发式判断, 快且零成本。判断"是 URL 还是原文"这种事
  用不着模型。
- 失败时不 raise, 而是往 state['errors'] 里塞错误信息, 让上层 CLI 决定怎么处理
  (通常是提示用户手动粘贴 JD 文本)。节点内部 raise 会中断整张图, 不利于给用户
  友好提示。
"""
from jdscout.state import AgentState
from jdscout.tools import web_scraper


async def fetch_jd(state: AgentState) -> dict:
    """获取 JD 纯文本。

    分支:
      1. jd_input 是 URL: 调 web_scraper 抓; 抓到内容 < 200 字符视为被反爬拦截
      2. jd_input 是纯文本(>= 200 字符): 直接用
      3. URL 抓失败 / 文本太短: 往 errors 里塞信息, 让用户手动粘贴
    """
    jd_input = state["jd_input"]

    if jd_input.startswith(("http://", "https://")):
        try:
            text = await web_scraper.fetch_and_extract(jd_input)
            if len(text) < 200:
                # 抓到了但内容过短 —— 多半是 SPA 空壳或被反爬挡了
                raise ValueError("Fetched content too short, likely blocked or JS-rendered")
        except Exception as e:
            return {"errors": [f"JD fetch failed: {e}. Please paste the JD text directly."]}
    else:
        text = jd_input  # 假设是原文
        if len(text) < 200:
            return {"errors": ["JD text too short (<200 chars). Provide the full JD."]}

    return {"jd_raw_text": text}
