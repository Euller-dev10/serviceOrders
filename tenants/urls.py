from django.urls import path

from tenants.views import BillingView

urlpatterns = [
    path('billing/', BillingView.as_view(), name='billing'),
]
