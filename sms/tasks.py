from celery import shared_task


@shared_task(
    bind=True, queue="sms_sender", max_retries=3, retry_backoff=True, autoretry_for=(Exception,)
)
def send_normal_sms(self, sms_id: int):
    pass


@shared_task(
    bind=True, queue="sms_sender", max_retries=6, retry_backoff=True, autoretry_for=(Exception,)
)
def send_express_sms(self, sms_id: int):
    pass
