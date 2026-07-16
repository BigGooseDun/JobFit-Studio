"""JD 网页抓取。轻量版: httpx + BeautifulSoup。

选型 trade-off:
- 用 httpx 不用 requests: requests 只有同步 API, 塞进 async 节点会阻塞事件循环;
  httpx 原生支持 async(AsyncClient), 和 LangGraph 的 async 节点是同一套并发模型。
- 用 BeautifulSoup 不用正则: HTML 结构不规则, 正则提取脆弱; bs4 能可靠地按标签
  剥离 script/style/nav 这些噪音。
- 后续如果遇到 JS 渲染的网站(BOSS 直聘等 SPA), 再加 Playwright fallback(Phase 2)。
"""
import httpx
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


async def fetch_and_extract(url: str, timeout: int = 15) -> str:
    """抓取 URL, 提取主要文本内容。

    策略:
      1. 用 httpx 异步请求, 15 秒超时
      2. 用 BeautifulSoup 解析, 去掉 script/style/nav/footer 等噪音标签
      3. 提取剩余可见文本, 折叠连续空行

    抓不到就 raise(httpx 的 HTTPStatusError / 超时等), 由上层 fetch_jd 节点决定怎么处理。
    """
    async with httpx.AsyncClient(
        headers=HEADERS, timeout=timeout, follow_redirects=True
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # 去掉不承载正文的标签
    for tag in soup(["script", "style", "nav", "footer", "aside", "header"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    # 折叠连续空行
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)
