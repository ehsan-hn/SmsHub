from django.db.models import Sum

from account.models import User
from billing.models import Transaction, TransactionType
from sms.models import SMS


def create_charge_transaction(user: User, amount: int) -> Transaction:
    if amount < 0:
        raise ValueError("Amount must be positive")
    return Transaction.objects.create(user=user, amount=amount, type=TransactionType.CHARGE)


def create_refund_transaction(user: User, amount: int, sms: SMS) -> Transaction:
    if amount > 0:
        raise ValueError("Refund amount cannot be positive")
    return Transaction.objects.create(
        user=user, amount=amount, type=TransactionType.REFUND, sms=sms
    )


def create_deduct_transaction(user: User, amount: int, sms: SMS) -> Transaction:
    if amount > 0:
        raise ValueError("Deduct amount cannot be positive")
    return Transaction.objects.create(
        user=user, amount=amount, type=TransactionType.SMS_DEDUCTION, sms=sms
    )


def get_user_balance(user: User) -> int:
    return Transaction.objects.filter(user=user).aggregate(Sum("amount"))["amount__sum"] or 0
