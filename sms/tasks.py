from celery import shared_task
from django.utils.timezone import now

from sms.models import SMS, SMSStatus


class API:
    def send(self, **kwargs):
        # TODO: Implement actual API integration
        return {}


def _send_sms_internal(sms: SMS) -> None:
    api = API()
    params = {
        "receptor": sms.receiver,
        "message": sms.content,
        "sender": sms.sender,
        "localid": sms.id,
    }

    try:
        response = api.send(**params)
        sms.status = SMSStatus.SENT
        sms.message_id = response.get("message_id") if isinstance(response, dict) else None
    except Exception as e:
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
