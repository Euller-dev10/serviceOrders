"""Registro de tools — contrato §9.3 do PRD."""

from __future__ import annotations

from typing import Any, Callable

from ai.tools.schemas import (
    AggregateServiceOrdersInput,
    DraftServiceReportInput,
    GetClientInput,
    GetServiceOrderInput,
    ListScaleHistoryInput,
    SearchServiceOrdersInput,
)
from ai.tools.service_order_tools import (
    ToolError,
    aggregate_service_orders,
    draft_service_report,
    get_client,
    get_service_order,
    list_scale_history,
    search_service_orders,
)

TOOLS: dict[str, Callable[..., dict]] = {
    'search_service_orders': search_service_orders,
    'get_service_order': get_service_order,
    'get_client': get_client,
    'list_scale_history': list_scale_history,
    'aggregate_service_orders': aggregate_service_orders,
    'draft_service_report': draft_service_report,
}

TOOL_SCHEMAS: dict[str, type] = {
    'search_service_orders': SearchServiceOrdersInput,
    'get_service_order': GetServiceOrderInput,
    'get_client': GetClientInput,
    'list_scale_history': ListScaleHistoryInput,
    'aggregate_service_orders': AggregateServiceOrdersInput,
    'draft_service_report': DraftServiceReportInput,
}

TOOL_DESCRIPTIONS: dict[str, str] = {
    'search_service_orders': 'Lista ordens de serviço com filtros (cliente, período, tipo de serviço).',
    'get_service_order': 'Detalha uma ordem de serviço por número ou id.',
    'get_client': 'Consulta cliente por documento ou id.',
    'list_scale_history': 'Histórico de ordens de serviço de uma balança.',
    'aggregate_service_orders': 'Agrega ordens de serviço (por cliente, dia, flag de serviço ou selo).',
    'draft_service_report': 'Gera rascunho de laudo/observação a partir de uma O.S.',
}


def get_tool(name: str) -> Callable[..., dict]:
    if name not in TOOLS:
        raise ToolError(f'Ferramenta desconhecida: {name}')
    return TOOLS[name]


def list_tools() -> list[dict]:
    return [
        {
            'name': name,
            'description': TOOL_DESCRIPTIONS.get(name, ''),
            'parameters': TOOL_SCHEMAS[name].model_json_schema() if name in TOOL_SCHEMAS else {},
        }
        for name in sorted(TOOLS)
    ]


def run_tool(name: str, args: dict | None, *, tenant_id: int, **runtime) -> Any:
    """Executa tool com tenant_id injetado — args do LLM nunca contêm tenant."""
    fn = get_tool(name)
    schema = TOOL_SCHEMAS.get(name)
    clean_args: dict = dict(args or {})
    # Remove chaves que o LLM não deveria enviar (segurança multi-tenant)
    clean_args.pop('tenant_id', None)
    clean_args.pop('user_id', None)
    clean_args.pop('user_role', None)
    clean_args.pop('tenant', None)

    if schema is not None:
        validated = schema.model_validate(clean_args)
        clean_args = validated.model_dump()

    try:
        return fn(tenant_id=tenant_id, **clean_args, **runtime)
    except ToolError:
        raise
    except Exception:
        raise ToolError('Não foi possível executar a ferramenta. Tente novamente.') from None
