from django.urls import path

from sms.views import SendSMSView

app_name = "sms"

urlpatterns = [
    path("v1/send", SendSMSView.as_view(), name="send_sms"),
]
