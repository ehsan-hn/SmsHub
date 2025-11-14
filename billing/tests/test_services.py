from unittest.mock import patch

from django.test import TestCase, TransactionTestCase

from account.models import User
from billing.exceptions import InsufficientFundsError
from billing.models import TransactionType
from billing.services import (
    _get_balance_key,
    _update_balance_cache,
    _update_user_balance,
    create_charge_transaction,
    create_deduct_transaction,
    create_refund_transaction,
    create_transaction,
    get_user_balance,
    update_transaction_sms_field,
)
from sms.models import SMS, SMSStatus


class BillingServicesTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.user.balance = 10000
        self.user.save()

    def test_get_balance_key(self):
        """Test that balance key is formatted correctly"""
        key = _get_balance_key(self.user.id)
        self.assertEqual(key, f"user_balance:{self.user.id}")

    @patch("billing.services.redis_conn")
    def test_update_balance_cache(self, mock_redis):
        """Test that balance cache is updated correctly"""
        _update_balance_cache(self.user.id, 5000)
        mock_redis.set.assert_called_once_with(f"user_balance:{self.user.id}", 5000)

    def test_update_user_balance(self):
        """Test that user balance is updated atomically"""
        initial_balance = self.user.balance
        amount_delta = 5000

        updated_user = _update_user_balance(self.user, amount_delta)
        self.assertEqual(updated_user.balance, initial_balance + amount_delta)

        # Verify in database
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, initial_balance + amount_delta)

    def test_create_transaction(self):
        """Test creating a basic transaction"""
        tx = create_transaction(
            user=self.user, amount=1000, transaction_type=TransactionType.CHARGE
        )

        self.assertIsNotNone(tx.id)
        self.assertEqual(tx.user, self.user)
        self.assertEqual(tx.amount, 1000)
        self.assertEqual(tx.type, TransactionType.CHARGE)
        self.assertIsNone(tx.sms)

    def test_create_transaction_with_sms(self):
        """Test creating a transaction with SMS"""
        sms = SMS.objects.create(
            user=self.user,
            sender="100001",
            receiver="09120000001",
            content="Test message",
            cost=1000,
            status=SMSStatus.CREATED,
        )

        tx = create_transaction(
            user=self.user,
            amount=-1000,
            transaction_type=TransactionType.SMS_DEDUCTION,
            sms=sms,
        )

        self.assertEqual(tx.sms, sms)
        self.assertEqual(tx.amount, -1000)

    def test_create_charge_transaction(self):
        """Test creating a charge transaction"""
        initial_balance = self.user.balance
        charge_amount = 5000

        tx = create_charge_transaction(self.user, charge_amount)

        self.assertIsNotNone(tx.id)
        self.assertEqual(tx.type, TransactionType.CHARGE)
        self.assertEqual(tx.amount, charge_amount)
        self.assertEqual(tx.user, self.user)

        # Verify balance was updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, initial_balance + charge_amount)

    def test_create_charge_transaction_negative_amount(self):
        """Test that charge transaction raises error for negative amount"""
        with self.assertRaises(ValueError) as context:
            create_charge_transaction(self.user, -1000)

        self.assertIn("Amount must be positive", str(context.exception))

    def test_create_charge_transaction_zero_amount(self):
        """Test that charge transaction raises error for zero amount"""
        with self.assertRaises(ValueError) as context:
            create_charge_transaction(self.user, 0)

        self.assertIn("Amount must be positive", str(context.exception))

    def test_create_refund_transaction(self):
        """Test creating a refund transaction"""
        initial_balance = self.user.balance
        refund_amount = 2000

        sms = SMS.objects.create(
            user=self.user,
            sender="100001",
            receiver="09120000001",
            content="Test message",
            cost=2000,
            status=SMSStatus.FAILED,
        )

        tx = create_refund_transaction(self.user, refund_amount, sms)

        self.assertIsNotNone(tx.id)
        self.assertEqual(tx.type, TransactionType.REFUND)
        self.assertEqual(tx.amount, refund_amount)
        self.assertEqual(tx.user, self.user)
        self.assertEqual(tx.sms, sms)

        # Verify balance was updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, initial_balance + refund_amount)

    def test_create_refund_transaction_negative_amount(self):
        sms = SMS.objects.create(
            user=self.user,
            sender="100001",
            receiver="09120000001",
            content="Test message",
            cost=1000,
            status=SMSStatus.FAILED,
        )

        with self.assertRaises(ValueError) as context:
            create_refund_transaction(self.user, -1000, sms)

        self.assertIn("Amount must be positive", str(context.exception))

    def test_create_deduct_transaction(self):
        """Test creating a deduct transaction"""
        initial_balance = self.user.balance
        deduct_amount = 3000

        tx = create_deduct_transaction(self.user, deduct_amount)

        self.assertIsNotNone(tx.id)
        self.assertEqual(tx.type, TransactionType.SMS_DEDUCTION)
        self.assertEqual(tx.amount, -deduct_amount)
        self.assertEqual(tx.user, self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, initial_balance - deduct_amount)

    def test_create_deduct_transaction_insufficient_funds(self):
        """Test that deduct transaction raises error when balance is insufficient"""
        self.user.balance = 1000
        self.user.save()

        with self.assertRaises(InsufficientFundsError) as context:
            create_deduct_transaction(self.user, 2000)

        self.assertIn("Insufficient funds", str(context.exception))

        # Verify balance was not changed
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, 1000)

    def test_create_deduct_transaction_exact_balance(self):
        """Test deducting exact balance amount"""
        self.user.balance = 1000
        self.user.save()

        tx = create_deduct_transaction(self.user, 1000)

        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, 0)
        self.assertEqual(tx.amount, -1000)

    def test_create_deduct_transaction_negative_amount(self):
        """Test that deduct transaction raises error for negative amount"""
        with self.assertRaises(ValueError) as context:
            create_deduct_transaction(self.user, -1000)

        self.assertIn("Amount must be positive", str(context.exception))

    def test_create_deduct_transaction_zero_amount(self):
        """Test that deduct transaction raises error for zero amount"""
        with self.assertRaises(ValueError) as context:
            create_deduct_transaction(self.user, 0)

        self.assertIn("Amount must be positive", str(context.exception))

    def test_update_transaction_sms_field(self):
        """Test updating transaction SMS field"""
        tx = create_transaction(
            user=self.user, amount=-1000, transaction_type=TransactionType.SMS_DEDUCTION
        )

        sms = SMS.objects.create(
            user=self.user,
            sender="100001",
            receiver="09120000001",
            content="Test message",
            cost=1000,
            status=SMSStatus.CREATED,
        )

        updated_tx = update_transaction_sms_field(tx, sms)

        self.assertEqual(updated_tx.sms, sms)
        tx.refresh_from_db()
        self.assertEqual(tx.sms, sms)

    @patch("billing.services.redis_conn")
    def test_get_user_balance_from_cache(self, mock_redis):
        """Test getting user balance from Redis cache"""
        mock_redis.get.return_value = 15000

        balance = get_user_balance(self.user)

        self.assertEqual(balance, 15000)
        mock_redis.get.assert_called_once_with(f"user_balance:{self.user.id}")
        # Should not refresh from DB when cache hit
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.balance, 15000)

    @patch("billing.services.redis_conn")
    def test_get_user_balance_from_db_when_cache_miss(self, mock_redis):
        """Test getting user balance from DB when cache misses"""
        mock_redis.get.return_value = None
        self.user.balance = 25000
        self.user.save()

        balance = get_user_balance(self.user)

        self.assertEqual(balance, 25000)
        mock_redis.get.assert_called_once_with(f"user_balance:{self.user.id}")
        # Should set cache after DB fetch
        mock_redis.set.assert_called_once_with(f"user_balance:{self.user.id}", 25000)

    @patch("billing.services.redis_conn")
    def test_get_user_balance_cache_set_on_miss(self, mock_redis):
        """Test that cache is set when retrieving from DB"""
        mock_redis.get.return_value = None
        self.user.balance = 30000
        self.user.save()

        balance = get_user_balance(self.user)

        self.assertEqual(balance, 30000)
        mock_redis.set.assert_called_once_with(f"user_balance:{self.user.id}", 30000)


class BillingServicesConcurrencyTestCase(TransactionTestCase):
    """Test cases for concurrent transaction scenarios"""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.user.balance = 10000
        self.user.save()

    def test_multiple_charges_accumulate(self):
        """Test that multiple charges accumulate correctly"""
        create_charge_transaction(self.user, 1000)
        create_charge_transaction(self.user, 2000)
        create_charge_transaction(self.user, 3000)

        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, 16000)

    def test_multiple_deductions_accumulate(self):
        """Test that multiple deductions accumulate correctly"""
        create_deduct_transaction(self.user, 2000)
        create_deduct_transaction(self.user, 3000)

        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, 5000)

    def test_charge_and_deduct_sequence(self):
        """Test a sequence of charges and deductions"""
        create_charge_transaction(self.user, 5000)
        create_deduct_transaction(self.user, 2000)
        create_charge_transaction(self.user, 1000)
        create_deduct_transaction(self.user, 3000)

        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, 11000)
