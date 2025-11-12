from django.utils.translation import gettext_lazy as _
from rest_framework import serializers


class SendSMSSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    receiver = serializers.RegexField(
        label=_("Receiver Phone Number"),
        regex=r"^\?\d{9,15}$",
        max_length=20,
        error_messages={
            "invalid": _("Invalid phone number format. Must be a valid number, e.g., 98912345678.")
        },
    )
    content = serializers.CharField(
        label=_("Message Content"),
        max_length=480,
        allow_blank=False,
        style={"base_template": "textarea.html"},
    )
    is_express = serializers.BooleanField(default=False)
