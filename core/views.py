from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from core.permissions import admin_required
from core.privacy import anonymize_client, export_client_data
from service_order.models import Client


def _client_for_request(request, pk):
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    client = Client.objects.filter(pk=pk, tenant=tenant).first()
    if client is None:
        raise Http404
    return client


@admin_required
@require_GET
def client_data_export_view(request, pk):
    client = _client_for_request(request, pk)
    return JsonResponse(export_client_data(client=client, actor=request.user, request=request))


@admin_required
@require_POST
def client_anonymize_view(request, pk):
    client = _client_for_request(request, pk)
    anonymize_client(client=client, actor=request.user, request=request)
    return JsonResponse({'ok': True, 'client_id': client.pk, 'message': 'Dados anonimizados.'})
