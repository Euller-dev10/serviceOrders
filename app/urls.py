from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from service_order.views import HomeView, ClientListView, NewClientCreateView, NewScaleCreateView, ScaleListView,ServiceOrderView, ClientDetailView, ScaleDetailView, ServiceOrderListView, ServiceOrderDetailView, ServiceOrderPrintView, TechnicalReportView, TechnicalReportPrintView, TechnicalReportListView, TechnicalReportDeleteView, TechnicalReportCancelView, TechnicalReportReopenView, ClientUpdateView, ScaleUpdateView, ServiceOrderUpdateView, ScaleDeleteView, ClientDeleteView, ServiceOrderDeleteView, StampListView, StampCreateView, StampDeliveryCreateView, StampBulkDeliveryView, StampDamageView, DashboardView, ServiceOrderExportView
from accounts.views import register_view, login_view, logout_view, user_list_view, user_invite_view, user_edit_view, invite_accept_view
from core.views import client_data_export_view, client_anonymize_view


urlpatterns = [
    path('',HomeView.as_view(), name='home'),
    path('admin/', admin.site.urls, name='admin'),
    path('select2/', include('django_select2.urls')),
    path('search_client/', ClientListView.as_view(), name='search_client'),
    path('new_client/', NewClientCreateView.as_view(), name='new_client'),
    path('new_scale/', NewScaleCreateView.as_view(), name='new_scale'),
    path('search_scale/', ScaleListView.as_view(), name='search_scale'),
    path('client_detail/<int:pk>/', ClientDetailView.as_view(), name='client_detail'),
    path('scale_detail/<int:pk>/',ScaleDetailView.as_view(), name='scale_detail' ),
    path('service_order/<int:id_client>/<int:id_scale>/', ServiceOrderView.as_view(), name='service_order'),
    path('list_os/', ServiceOrderListView.as_view(), name='list_os'),
    path('os_detail/<int:pk>/', ServiceOrderDetailView.as_view(), name='os_detail'),
    path('os/<int:pk>/imprimir/', ServiceOrderPrintView.as_view(), name='os_print'),
    path('os/<int:pk>/relatorio-tecnico/', TechnicalReportView.as_view(), name='technical_report'),
    path('relatorios-tecnicos/', TechnicalReportListView.as_view(), name='technical_report_list'),
    path('relatorios-tecnicos/<int:pk>/excluir/', TechnicalReportDeleteView.as_view(), name='technical_report_delete'),
    path('os/<int:pk>/relatorio-tecnico/imprimir/', TechnicalReportPrintView.as_view(), name='technical_report_print'),
    path('os/<int:pk>/relatorio-tecnico/cancelar/', TechnicalReportCancelView.as_view(), name='technical_report_cancel'),
    path('os/<int:pk>/relatorio-tecnico/reabrir/', TechnicalReportReopenView.as_view(), name='technical_report_reopen'),
    path('client_update/<int:pk>/update', ClientUpdateView.as_view(), name='client_update'),
    path('client_delete/<int:pk>/', ClientDeleteView.as_view(), name='client_delete'),
    path('scale_update/<int:pk>/update', ScaleUpdateView.as_view(), name='scale_update'),
    path('os_update/<int:pk>/update', ServiceOrderUpdateView.as_view(), name='os_update'),
    path('os/<int:pk>/excluir/', ServiceOrderDeleteView.as_view(), name='os_delete'),
    path('scale_delete/<int:pk>/scale', ScaleDeleteView.as_view(), name='scale_delete'),
    path('selos/', StampListView.as_view(), name='stamp_list'),
    path('selos/novo/', StampCreateView.as_view(), name='stamp_create'),
    path('selos/distribuir/', StampDeliveryCreateView.as_view(), name='stamp_distribute'),
    path('selos/distribuir-lote/', StampBulkDeliveryView.as_view(), name='stamp_bulk_distribute'),
    path('selos/<int:pk>/danificar/', StampDamageView.as_view(), name='stamp_damage'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('export/os/', ServiceOrderExportView.as_view(), name='os_export'),
    path('usuarios/', user_list_view, name='user_list'),
    path('usuarios/novo/', user_invite_view, name='user_invite'),
    path('usuarios/<int:pk>/editar/', user_edit_view, name='user_edit'),
    path('convite/<str:token>/', invite_accept_view, name='invite_accept'),
    path('privacidade/clientes/<int:pk>/exportar/', client_data_export_view, name='client_data_export'),
    path('privacidade/clientes/<int:pk>/anonimizar/', client_anonymize_view, name='client_anonymize'),
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('', include('ai.urls')),
    path('', include('tenants.urls')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
