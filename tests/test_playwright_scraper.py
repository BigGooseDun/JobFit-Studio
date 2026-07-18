"""fetch_jd 分层抓取策略的单元测试。

用 mock 模拟 httpx / Playwright 两层, 不真的起浏览器(CI 里起浏览器会失败或极慢)。
真实 Playwright 抓取放在 RUN_E2E 门控的测试里, 默认跳过。
"""
import os
from unittest.mock import AsyncMock

import pytest

from jdscout.nodes import fetch_jd as fetch_module
from jdscout.tools import web_scraper


def _patch(monkeypatch, *, static=None, static_exc=None, dynamic=None, dynamic_exc=None):
    static_mock = AsyncMock(side_effect=static_exc) if static_exc else AsyncMock(return_value=static)
    dynamic_mock = AsyncMock(side_effect=dynamic_exc) if dynamic_exc else AsyncMock(return_value=dynamic)
    monkeypatch.setattr(web_scraper, "fetch_and_extract", static_mock)
    monkeypatch.setattr(web_scraper, "fetch_with_playwright", dynamic_mock)
    return static_mock, dynamic_mock


@pytest.mark.asyncio
async def test_static_success_skips_playwright(monkeypatch):
    """httpx 抓到足够正文 -> 不起 Playwright。"""
    static, dynamic = _patch(monkeypatch, static="J" * 600)
    out = await fetch_module.fetch_jd({"jd_input": "https://jobs.example.com/1"})
    assert out["jd_raw_text"] == "J" * 600
    static.assert_awaited_once()
    dynamic.assert_not_awaited()   # 静态够长, 不该 fallback


@pytest.mark.asyncio
async def test_short_static_falls_back_to_playwright(monkeypatch):
    """httpx 正文过短(SPA 空壳)-> fallback 到 Playwright。"""
    static, dynamic = _patch(monkeypatch, static="short", dynamic="D" * 800)
    out = await fetch_module.fetch_jd({"jd_input": "https://jobs.lever.co/acme/xyz"})
    assert out["jd_raw_text"] == "D" * 800
    dynamic.assert_awaited_once()


@pytest.mark.asyncio
async def test_static_error_falls_back_to_playwright(monkeypatch):
    """httpx 报错(4xx/超时)-> fallback 到 Playwright。"""
    static, dynamic = _patch(monkeypatch, static_exc=RuntimeError("403"), dynamic="D" * 800)
    out = await fetch_module.fetch_jd({"jd_input": "https://boards.greenhouse.io/acme/1"})
    assert out["jd_raw_text"] == "D" * 800
    dynamic.assert_awaited_once()


@pytest.mark.asyncio
async def test_both_fail_returns_error(monkeypatch):
    """两层都失败 -> 提示用户手动粘 JD。"""
    _patch(monkeypatch, static_exc=RuntimeError("403"), dynamic_exc=RuntimeError("timeout"))
    out = await fetch_module.fetch_jd({"jd_input": "https://www.zhipin.com/job/1"})
    assert "jd_raw_text" not in out
    assert "paste the JD text directly" in out["errors"][0]


@pytest.mark.asyncio
async def test_raw_text_input_bypasses_scraping(monkeypatch):
    """非 URL 的原文输入直接用, 不碰抓取。"""
    static, dynamic = _patch(monkeypatch, static="x", dynamic="y")
    out = await fetch_module.fetch_jd({"jd_input": "岗位职责: " + "内容" * 100})
    assert out["jd_raw_text"].startswith("岗位职责")
    static.assert_not_awaited()
    dynamic.assert_not_awaited()


@pytest.mark.skipif(os.getenv("RUN_E2E") != "1", reason="真实 Playwright 抓取需 RUN_E2E=1")
@pytest.mark.asyncio
async def test_real_playwright_fetch():
    """真实起浏览器抓一个公开 Lever 页(手动 e2e, 默认跳过)。"""
    text = await web_scraper.fetch_with_playwright("https://jobs.lever.co/lever")
    assert len(text) > 200
