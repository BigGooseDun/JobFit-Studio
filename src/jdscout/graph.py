"""JD-Scout 主图: fetch_jd → extract → analyze → advise。

MVP 阶段不加 checkpointer(内存跑就行)。Phase 2 加 web UI 时再加 MemorySaver,
实现断点续跑。
"""
from langgraph.graph import StateGraph, START, END

from jdscout.state import AgentState
from jdscout.nodes.fetch_jd import fetch_jd
from jdscout.nodes.extract import extract
from jdscout.nodes.analyze import analyze
from jdscout.nodes.advise import advise


def build_graph():
    """构建 JD-Scout 主图: fetch_jd → extract → analyze → advise(线性四节点)。"""
    builder = StateGraph(AgentState)

    builder.add_node("fetch_jd", fetch_jd)
    builder.add_node("extract", extract)
    builder.add_node("analyze", analyze)
    builder.add_node("advise", advise)

    builder.add_edge(START, "fetch_jd")
    builder.add_edge("fetch_jd", "extract")
    builder.add_edge("extract", "analyze")
    builder.add_edge("analyze", "advise")
    builder.add_edge("advise", END)

    return builder.compile()


# 全局实例, CLI 和后续 web server 都复用它
graph = build_graph()
