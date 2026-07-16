"""结构化 LLM 调用的有限重试封装。

为什么需要(真实观测):DeepSeek 的 function_calling 偶发不返回有效 tool call,
with_structured_output 这时会静默给 None; 短时高频调用也可能被限流。单次调用不稳定,
端到端四节点里任意一个偶发失败就会毁掉整份报告 —— 实测 Docker 连续跑, 每次挂的还是
不同节点(时而 analyze 时而 advise), 说明是随机性失败, 重试能救。

设计:
- 有限次重试(默认 3 次), 失败原因(None 或异常)都触发重试。
- 指数退避(0.5s, 1.0s...), 给限流一点喘息, 也避免瞬时抖动。
- 全部用尽仍失败就 raise, 由节点转成 state['errors'] —— 不做无限重试, 失败该上报。
"""
import asyncio


async def ainvoke_structured_with_retry(
    structured_model,
    prompt: str,
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
):
    """调用 structured_model.ainvoke(prompt), 对 None 结果和异常做有限次重试。"""
    last_reason = "unknown error"
    for i in range(attempts):
        try:
            result = await structured_model.ainvoke(prompt)
            if result is not None:
                return result
            last_reason = "model returned no structured output (possibly truncated)"
        except Exception as e:  # noqa: BLE001 —— 故意兜底: 各种网络/解析异常都重试
            last_reason = str(e)
        if i < attempts - 1:
            await asyncio.sleep(base_delay * (i + 1))
    raise RuntimeError(f"after {attempts} attempts: {last_reason}")
