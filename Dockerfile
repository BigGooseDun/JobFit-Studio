# 基于 python:3.11-slim(体积小, 和本地开发的 3.11 一致, 避免版本漂移)。
FROM python:3.11-slim

# 从官方镜像直接拷 uv 二进制进来 —— 比 pip install uv 快, 且版本可钉。
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# ---- 分层缓存的关键 ----
# 先只拷依赖清单, 再装依赖。这一层只有 pyproject.toml / uv.lock 变了才会失效;
# 只改业务代码时, 这一层命中缓存, 不用重装依赖 —— 构建快很多。
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# 再拷源码。业务代码常变, 放在依赖层之后, 改代码不影响上面的依赖缓存。
COPY src/ ./src/
# 把项目本身装进环境(editable), 让 `python -m jdscout.cli` 能 import。
RUN uv sync --frozen --no-dev

ENV PYTHONUNBUFFERED=1

# 用 uv run 起 CLI; --jd/--resume 等参数在 docker run 时追加, 会拼到这后面。
# --no-sync: 依赖已在 build 阶段装好, 运行时不要再重新 sync(否则每次启动都重装一遍、
# 拖慢启动还刷屏)。
ENTRYPOINT ["uv", "run", "--no-sync", "python", "-m", "jdscout.cli"]
