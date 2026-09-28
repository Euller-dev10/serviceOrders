"""Compilador do grafo LangGraph + checkpointer (PG em prod, memória em teste)."""

from __future__ import annotations

from typing import Any, Callable, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from ai.graph.nodes import (
    condense_history_node,
    persist_node,
    resolve_config_node,
    retrieve_node,
    router_node,
    synthesize_node,
    tools_node,
)
from ai.graph.state import AgentState


def _route_after_router(state: AgentState) -> str:
    route = state.get('route') or 'direct'
    if route == 'tools':
        return 'tools'
    if route == 'retrieve':
        return 'retrieve'
    return 'synthesize'


def build_graph(checkpointer: Optional[Any] = None) -> Callable:
    """Montia: resolve_config → condense_history → router → (tools|retrieve) → synthesize → persist."""
    workflow = StateGraph(AgentState)

    workflow.add_node('resolve_config', resolve_config_node)
    workflow.add_node('condense_history', condense_history_node)
    workflow.add_node('router', router_node)
    workflow.add_node('tools', tools_node)
    workflow.add_node('retrieve', retrieve_node)
    workflow.add_node('synthesize', synthesize_node)
    workflow.add_node('persist', persist_node)

    workflow.set_entry_point('resolve_config')
    workflow.add_edge('resolve_config', 'condense_history')
    workflow.add_edge('condense_history', 'router')

    workflow.add_conditional_edges(
        'router',
        _route_after_router,
        {
            'tools': 'tools',
            'retrieve': 'retrieve',
            'synthesize': 'synthesize',
        },
    )
    workflow.add_edge('tools', 'synthesize')
    workflow.add_edge('retrieve', 'synthesize')
    workflow.add_edge('synthesize', 'persist')
    workflow.add_edge('persist', END)

    return workflow.compile(checkpointer=checkpointer or MemorySaver())


def get_checkpointer():
    """PostgresSaver quando houver DB PG; senão MemorySaver (testes SQLite)."""
    try:
        from django.db import connections

        if connections['default'].vendor != 'postgresql':
            return MemorySaver()
        from langgraph.checkpoint.postgres import PostgresSaver

        conn = connections['default']
        # PostgresSaver aceita string de conexão ou connection
        dsn = (
            f'postgresql://{conn.settings_dict.get("USER", "")}:'
            f'{conn.settings_dict.get("PASSWORD", "")}@'
            f'{conn.settings_dict.get("HOST", "localhost")}:'
            f'{conn.settings_dict.get("PORT", "5432")}/'
            f'{conn.settings_dict.get("NAME", "")}'
        )
        global _checkpointer_context
        _checkpointer_context = PostgresSaver.from_conn_string(dsn)
        checkpointer = _checkpointer_context.__enter__()
        checkpointer.setup()
        return checkpointer
    except Exception:
        if _checkpointer_context is not None:
            _checkpointer_context.__exit__(None, None, None)
            _checkpointer_context = None
        raise


# Instância lazy (evita abrir conexão no import)
_graph = None
_checkpointer_context = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph(checkpointer=get_checkpointer())
    return _graph


def run_agent(state: dict, config: dict | None = None) -> dict:
    """Executa o grafo e devolve o estado final."""
    graph = get_graph()
    cfg = config or {'configurable': {'thread_id': f'session-{state.get("session_id", 0)}'}}
    final = graph.invoke(state, cfg)
    return dict(final) if final else {}
