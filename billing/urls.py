from django.urls import path

from billing.views import ChargeView

app_name = "billing"

urlpatterns = [
    path("v1/charge", ChargeView.as_view(), name="charge"),
]
