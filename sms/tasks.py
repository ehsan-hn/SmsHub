from celery import shared_task
from django.conf import settings
from django.utils.timezone import now

from sms.models import SMS, SMSStatus
from sms.services import (
    deliver_sms,
    fail_sms,
    get_magfa_sms_to_check_status,
    get_sms_by_mid,
    get_sms_with_over_24_hours_of_sent_status,
)
from sms.sms_provider_clients.magfa import MagfaProvider
from sms.utils import get_client_api


def _send_sms_internal(sms: SMS) -> None:
    api = get_client_api(sms.sender)

    try:
        response = api.send_sms(
            sender=sms.sender,
            destination=sms.receiver,
            message=sms.content,
            uid=sms.id,
        )

        top_level_status = response.get("status")

        if top_level_status == 0:
            messages_list = response.get("messages", [])

            if messages_list and len(messages_list) > 0:
                msg_info = messages_list[0]
                inner_status = msg_info.get("status")

                if inner_status == 0:
                    sms.status = SMSStatus.SENT
                    sms.message_id = msg_info.get("id")
                    sms.service_error = None
                else:
                    sms.status = SMSStatus.FAILED
                    sms.service_error = f"Msg Status: {inner_status}"
            else:
                sms.status = SMSStatus.FAILED
                sms.service_error = "API Anomaly: Status 0 but no message info"

        else:
            sms.status = SMSStatus.FAILED
            sms.service_error = f"API Status: {top_level_status}"

    except Exception as e:
        sms.status = SMSStatus.FAILED
        sms.service_error = str(e)
        raise
    finally:
        sms.last_attempt_time = now()
        sms.attempts_num += 1
        sms.save()


@shared_task(
    bind=True,
    queue="standard_sms_sender",
    max_retries=3,
    retry_backoff=True,
    autoretry_for=(Exception,),
)
def send_normal_sms(self, sms_id: int) -> bool:
    sms = SMS.objects.get(pk=sms_id)
    _send_sms_internal(sms)
    return True


@shared_task(
    bind=True,
    queue="express_sms_sender",
    max_retries=6,
    retry_backoff=True,
    autoretry_for=(Exception,),
)
def send_express_sms(self, sms_id: int) -> bool:
    sms = SMS.objects.get(pk=sms_id)
    _send_sms_internal(sms)
    return True


def check_sent_sms_status_for_magfa():
    for sms in get_sms_with_over_24_hours_of_sent_status():
        fail_sms(sms)
    list_of_sms = get_magfa_sms_to_check_status()
    for i in range(0, list_of_sms.count(), 100):
        api = MagfaProvider(settings.MAGFA_USERNAME, settings.MAGFA_PASSWORD, settings.MAGFA_DOMAIN)
        mids = list(list_of_sms[i : i + 100].values_list("message_id", flat=True))
        try:
            response = api.get_statuses(mids)
            for message_data in response.get("dlrs"):
                sms = get_sms_by_mid(message_data.get("mid"))
                if message_data.get("status") == -1:
                    fail_sms(sms)
                elif message_data.get("status") in [1, 2]:
                    deliver_sms(sms)
        except Exception:
            pass
