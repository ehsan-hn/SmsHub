import django_filters

from sms.models import SMS, SMSStatus


class SMSReportFilterSet(django_filters.FilterSet):
    user_id = django_filters.NumberFilter(field_name="user_id", required=True)
    start_date = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    end_date = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    status = django_filters.ChoiceFilter(field_name="status", choices=SMSStatus.choices)
    receiver = django_filters.CharFilter(field_name="receiver")

    class Meta:
        model = SMS
        fields = ["user_id", "start_date", "end_date", "status", "receiver"]
