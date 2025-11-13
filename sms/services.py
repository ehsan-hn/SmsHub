from datetime import timedelta

from django.db import transaction
from django.utils.timezone import now

from account.models import User
from billing.services import (
    create_deduct_transaction,
    create_refund_transaction,
    update_transaction_sms_field,
)
from sms.models import SMS, SMSStatus


def _calculate_sms_cost(content: str, sender: str, receiver: str, is_express: bool) -> int:
    # TODO calculate base on sender operator fee and content and receiver location (for international numbers)
    if is_express:
        return 1500  # in Rial
    else:
        return 1000  # in Rial


def _get_sender_number(user: User) -> str:
    return "100002"


def create_sms(
    user: User,
    content: str,
    sender: str,
    receiver: str,
    cost: int,
    is_express: bool = False,
) -> SMS:
    sms = SMS.objects.create(
        user=user,
        sender=sender,
        receiver=receiver,
        content=content,
        cost=cost,
        status=SMSStatus.CREATED,
        is_express=is_express,
    )
    return sms


@transaction.atomic
def create_sms_and_deduct_balance(user, content, receiver, is_express=False) -> SMS:
    sender_number = _get_sender_number(user)
    cost = _calculate_sms_cost(content, sender_number, receiver, is_express)
    tx = create_deduct_transaction(user=user, amount=cost)
    sms = create_sms(user, content, sender_number, receiver, cost, is_express=is_express)
    update_transaction_sms_field(tx, sms)
    return sms


def send_sms(sms: SMS, forced: bool = False):
    from sms.tasks import send_express_sms, send_normal_sms

    if not forced and sms.status not in [SMSStatus.CREATED, SMSStatus.FAILED]:
        raise Exception(f"SMS status {sms.status} already added to queue")
    sms.status = SMSStatus.IN_QUEUE
    sms.save(update_fields=["status", "modified_at"])
    if sms.is_express:
        return send_express_sms.delay(sms.id)
    return send_normal_sms.delay(sms.id)


def get_magfa_sms_to_check_status():
    cut_off = now() - timedelta(hours=24)
    return SMS.objects.filter(
        status=SMSStatus.SENT, created_at__gte=cut_off, sender__startswith="3000"
    )


def get_sms_with_over_24_hours_of_sent_status():
    cut_off = now() - timedelta(hours=24)
    return SMS.objects.filter(status=SMSStatus.FAILED, created_at__gte=cut_off).update(
        status=SMSStatus.FAILED, modified_at=now()
    )


def fail_sms(sms: SMS):
    sms.status = SMSStatus.FAILED
    sms.save(update_fields=["status", "modified_at"])
    create_refund_transaction(sms.user, sms.cost, sms)


def deliver_sms(sms: SMS):
    sms.status = SMSStatus.DELIVERED
    sms.save(update_fields=["status", "modified_at"])


def get_sms_by_mid(mid: int):
    return SMS.objects.get(mid=mid)
