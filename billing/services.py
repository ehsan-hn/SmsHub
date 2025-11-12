from django.db import transaction
from django.db.models import F
from django_redis import get_redis_connection

from account.models import User
from billing.exceptions import InsufficientFundsError
from billing.models import Transaction, TransactionType
from sms.models import SMS

redis_conn = get_redis_connection("default")
BALANCE_KEY_TEMPLATE = "user_balance:{user_id}"


def _get_balance_key(user_id: int) -> str:
    return BALANCE_KEY_TEMPLATE.format(user_id=user_id)


def _update_balance_cache(user_id: int, balance: int) -> None:
    key = _get_balance_key(user_id)
    redis_conn.set(key, balance)


def _update_user_balance(user: User, amount_delta: int) -> User:
    user_to_update = User.objects.select_for_update().get(id=user.id)
    user_to_update.balance = F("balance") + amount_delta
    user_to_update.save(update_fields=["balance"])
    user_to_update.refresh_from_db(fields=["balance"])
    return user_to_update


def create_transaction(
    user: User,
    amount: int,
    transaction_type: str,
    sms: SMS = None,
) -> Transaction:
    if transaction_type == TransactionType.SMS_DEDUCTION:
        amount = -amount

    return Transaction.objects.create(
        user=user,
        amount=amount,
        type=transaction_type,
        sms=sms,
    )


@transaction.atomic
def create_charge_transaction(user: User, amount: int) -> Transaction:
    if amount <= 0:
        raise ValueError("Amount must be positive")

    user_updated = _update_user_balance(user, amount)
    tx = create_transaction(user_updated, amount, TransactionType.CHARGE)

    transaction.on_commit(lambda: _update_balance_cache(user_updated.id, user_updated.balance))
    return tx


@transaction.atomic
def create_refund_transaction(user: User, amount: int, sms: SMS) -> Transaction:
    if amount <= 0:
        raise ValueError("Amount must be positive")

    user_updated = _update_user_balance(user, amount)
    tx = create_transaction(user_updated, amount, TransactionType.REFUND, sms)

    transaction.on_commit(lambda: _update_balance_cache(user_updated.id, user_updated.balance))
    return tx


@transaction.atomic
def create_deduct_transaction(user: User, amount: int, sms: SMS) -> Transaction:
    if amount <= 0:
        raise ValueError("Amount must be positive")

    user_to_check = User.objects.select_for_update().get(id=user.id)
    if user_to_check.balance < amount:
        raise InsufficientFundsError("Insufficient funds for this SMS.")

    user_updated = _update_user_balance(user, -amount)
    tx = create_transaction(user_updated, amount, TransactionType.SMS_DEDUCTION, sms)

    transaction.on_commit(lambda: _update_balance_cache(user_updated.id, user_updated.balance))
    return tx


def get_user_balance(user: User) -> int:
    key = _get_balance_key(user.id)
    balance = redis_conn.get(key)

    if balance is None:
        user.refresh_from_db(fields=["balance"])
        balance = user.balance
        redis_conn.set(key, balance)

    return balance
