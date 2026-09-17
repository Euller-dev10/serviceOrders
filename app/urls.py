from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from service_order.views import HomeView, ClientListView, NewClientCreateView, NewScaleCreateView, ScaleListView,ServiceOrderView, ClientDetailView, ScaleDetailView, ServiceOrderListView, ServiceOrderDetailView, ClientUpdateView, ScaleUpdateView, ServiceOrderUpdateView, ScaleDeleteView
from accounts.views import register_view, login_view, logout_view


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
    path('client_update/<int:pk>/update', ClientUpdateView.as_view(), name='client_update'),
    path('scale_update/<int:pk>/update', ScaleUpdateView.as_view(), name='scale_update'),
    path('os_update/<int:pk>/update', ServiceOrderUpdateView.as_view(), name='os_update'),
    path('scale_delete/<int:pk>/scale', ScaleDeleteView.as_view(), name='scale_delete'),
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
