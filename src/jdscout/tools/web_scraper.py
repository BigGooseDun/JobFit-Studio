"""JD 网页抓取。分层策略: httpx 优先, Playwright fallback。

选型 trade-off:
- 用 httpx 不用 requests: requests 只有同步 API, 塞进 async 节点会阻塞事件循环;
  httpx 原生支持 async(AsyncClient), 和 LangGraph 的 async 节点是同一套并发模型。
- 用 BeautifulSoup 不用正则: HTML 结构不规则, 正则提取脆弱; bs4 能可靠地按标签
  剥离 script/style/nav 这些噪音。
- fallback 用 Playwright 不用 Selenium: 见 09-notes(现代、原生 async、维护活跃)。
  只有静态抓取失败/内容过短(多半是 SPA)才起浏览器 —— 起浏览器慢且重, 是最后手段。
"""
import httpx
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,en-US;q=0.9,en;q=0.8",
}


def _clean_html_to_text(html: str) -> str:
    """用 BeautifulSoup 剥离噪音标签, 提取可见正文, 折叠连续空行。"""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "aside", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


async def fetch_and_extract(url: str, timeout: int = 15) -> str:
    """静态抓取: httpx 拿 HTML + BeautifulSoup 提取正文。

    抓不到就 raise(httpx 的 HTTPStatusError / 超时等), 由上层 fetch_jd 决定是否 fallback。
    """
    async with httpx.AsyncClient(
        headers=HEADERS, timeout=timeout, follow_redirects=True
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    return _clean_html_to_text(resp.text)


async def fetch_with_playwright(url: str, timeout: int = 30000) -> str:
    """动态抓取 fallback: 用 headless Chromium 等 JS 渲染完再抓正文。

    适用: Lever / Greenhouse / Workday 等 SPA 招聘页(静态 HTML 是空壳)。
    - 等 networkidle, 让前端把 JD 渲染出来。
    - 抓 body innerText(浏览器已渲染的可见文本), 不用再 BeautifulSoup。
    - 每次用完关掉 context/browser, 不复用(避免 session 污染)。
    - 不做主动反爬伪装(不装绕过插件、不用第三方服务), 只设常规 UA/语言。
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                user_agent=HEADERS["User-Agent"],
                locale="zh-CN",
                extra_http_headers={"Accept-Language": HEADERS["Accept-Language"]},
            )
            page = await context.new_page()
            await page.goto(url, timeout=timeout)
            await page.wait_for_load_state("networkidle", timeout=timeout)
            text = await page.inner_text("body")
            await context.close()
        finally:
            await browser.close()

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)
