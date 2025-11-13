from django.urls import path

from sms.views import SendSMSView, SMSReportView

app_name = "sms"

urlpatterns = [
    path("v1/send", SendSMSView.as_view(), name="send_sms"),
    path("v1/report", SMSReportView.as_view(), name="sms_report"),
]
