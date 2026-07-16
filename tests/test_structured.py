"""ainvoke_structured_with_retry 的单元测试。base_delay=0 保持测试快。"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from jdscout.nodes._structured import ainvoke_structured_with_retry


@pytest.mark.asyncio
async def test_succeeds_first_try():
    sm = MagicMock()
    sm.ainvoke = AsyncMock(return_value="ok")
    result = await ainvoke_structured_with_retry(sm, "p", base_delay=0)
    assert result == "ok"
    assert sm.ainvoke.await_count == 1


@pytest.mark.asyncio
async def test_retries_on_none_then_succeeds():
    sm = MagicMock()
    sm.ainvoke = AsyncMock(side_effect=[None, "ok"])   # 第一次 None, 第二次成功
    result = await ainvoke_structured_with_retry(sm, "p", attempts=3, base_delay=0)
    assert result == "ok"
    assert sm.ainvoke.await_count == 2


@pytest.mark.asyncio
async def test_retries_on_exception_then_succeeds():
    sm = MagicMock()
    sm.ainvoke = AsyncMock(side_effect=[RuntimeError("transient"), "ok"])
    result = await ainvoke_structured_with_retry(sm, "p", attempts=3, base_delay=0)
    assert result == "ok"
    assert sm.ainvoke.await_count == 2


@pytest.mark.asyncio
async def test_exhausts_attempts_and_raises():
    sm = MagicMock()
    sm.ainvoke = AsyncMock(return_value=None)   # 一直 None
    with pytest.raises(RuntimeError, match="after 3 attempts"):
        await ainvoke_structured_with_retry(sm, "p", attempts=3, base_delay=0)
    assert sm.ainvoke.await_count == 3
