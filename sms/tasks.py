from celery import shared_task
from django.utils.timezone import now

from sms.models import SMS, SMSStatus
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
