"""缺口②：验证两层编排已落地为 LangGraph StateGraph + interrupt()。

不重复 E2E 行为测试（那部分由 test_e2e_milktea / test_graph_and_engine 覆盖），
这里只断言架构红线：外层/内层用 StateGraph 编译、干预图使用 interrupt()。
"""
from __future__ import annotations

from pathlib import Path

from app.agents.inner_graph import AgentCoordinator, build_agents
from app.engine.graph import build_outer_graph
from app.engine.intervention_graph import build_intervention_graph
from app.scenarios.loader import ScenarioLoader


def _is_compiled_graph(obj) -> bool:
    # LangGraph 编译产物是 Runnable 子类，且由 StateGraph.compile() 产出
    return hasattr(obj, "invoke") and hasattr(obj, "get_graph")


def _source():
    return ScenarioLoader("scenarios").load("milktea_startup")


def test_outer_graph_is_state_graph():
    graph = build_outer_graph(_source())
    assert _is_compiled_graph(graph)
    spec = graph.get_graph()
    node_names = {n for n in spec.nodes} if hasattr(spec, "nodes") else set()
    assert {"prepare", "apply_actions", "check_ending", "append_year"} <= node_names


def test_inner_coordinator_uses_state_graph():
    coordinator = AgentCoordinator(build_agents(_source(), use_stub=True))
    assert _is_compiled_graph(coordinator._graph)
    spec = coordinator._graph.get_graph()
    node_names = {n for n in spec.nodes} if hasattr(spec, "nodes") else set()
    assert {"observe", "propose", "validate", "emit"} <= node_names


def test_intervention_graph_uses_interrupt():
    graph = build_intervention_graph(_source())
    assert _is_compiled_graph(graph)
    # 源码中必须出现 interrupt()（架构红线）
    src = Path(__file__).parent.parent.joinpath(
        "app", "engine", "intervention_graph.py"
    ).read_text(encoding="utf-8")
    assert "from langgraph.types import interrupt" in src
    assert "interrupt(" in src


def test_source_file_imports_state_graph():
    graph_src = Path(__file__).parent.parent.joinpath(
        "app", "engine", "graph.py"
    ).read_text(encoding="utf-8")
    assert "from langgraph.graph import" in graph_src
    assert "StateGraph" in graph_src

    inner_src = Path(__file__).parent.parent.joinpath(
        "app", "agents", "inner_graph.py"
    ).read_text(encoding="utf-8")
    assert "StateGraph" in inner_src
