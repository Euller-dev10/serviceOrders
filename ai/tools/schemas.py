from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


class SearchServiceOrdersInput(BaseModel):
    client_cnpj: Optional[str] = Field(None, description='CNPJ/CPF do cliente (parcial ou completo)')
    client_name: Optional[str] = Field(None, description='Nome ou razão social do cliente')
    date_from: Optional[date] = Field(None, description='Data inicial (YYYY-MM-DD)')
    date_to: Optional[date] = Field(None, description='Data final (YYYY-MM-DD)')
    service_flag: Optional[Literal[
        'service1', 'service2', 'service3', 'service4',
        'service5', 'service6', 'service7', 'service8',
    ]] = Field(None, description='Flag de serviço (service1..service8)')
    verified: Optional[bool] = Field(None, description='Filtrar verificados pelo Inmetro')
    limit: int = Field(20, ge=1, description='Máximo de resultados (clamp ≤ 50)')


class GetServiceOrderInput(BaseModel):
    number: Optional[int] = Field(None, description='Número sequencial da O.S. no tenant')
    pk: Optional[int] = Field(None, description='ID interno da O.S.')


class GetClientInput(BaseModel):
    document: Optional[str] = Field(None, description='CNPJ/CPF do cliente')
    pk: Optional[int] = Field(None, description='ID interno do cliente')


class ListScaleHistoryInput(BaseModel):
    scale_pk: Optional[int] = Field(None, description='ID da balança')
    serial_number: Optional[str] = Field(None, description='Número de série da balança')
    limit: int = Field(20, ge=1, description='Máximo de resultados (clamp ≤ 50)')


class AggregateServiceOrdersInput(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    group_by: Literal['status', 'service_flag', 'client', 'day'] = Field(
        'service_flag', description='Dimensão de agregação'
    )


class DraftServiceReportInput(BaseModel):
    number: Optional[int] = Field(None, description='Número da O.S.')
    pk: Optional[int] = Field(None, description='ID da O.S.')
    tone: Literal['tecnico', 'resumido', 'cliente'] = Field(
        'tecnico', description='Tom do laudo'
    )
