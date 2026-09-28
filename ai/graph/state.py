from __future__ import annotations

from typing import Any, Optional, TypedDict


def merge_dicts(a: dict, b: dict) -> dict:
    return {**a, **b}


class AgentState(TypedDict, total=False):
    messages: list[dict]
    tenant_id: int
    user_id: int
    session_id: Optional[int]
    user_role: str
    user_role_code: str
    user_name: str
    tenant_name: str
    question: str
    route: str
    tool_results: list[dict]
    retrieved: list[dict]
    system_prompt: str
    summary: str
    condensed_messages: list[dict]
    answer: str
    provider: str
    model_name: str
    token_usage: dict
    cache_hit: bool
    fallback: bool
    error: Optional[str]
    config: dict[str, Any]
