from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class TransactionType(models.TextChoices):
    CHARGE = "charge", "شارژ حساب"
    REFUND = "refund", "استرداد"
    SMS_DEDUCTION = "sms_deduction", "کسر پیامک"


class Transaction(models.Model):
    user = models.ForeignKey(
        User, verbose_name="کاربر", on_delete=models.CASCADE, related_name="transactions"
    )
    type = models.CharField(
        verbose_name="نوع تراکنش", max_length=20, choices=TransactionType.choices, db_index=True
    )
    amount = models.BigIntegerField(verbose_name="مقدار")
    created_at = models.DateTimeField(verbose_name="زمان ایجاد", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "تراکنش"
        verbose_name_plural = "تراکنش‌ها"
        indexes = [
            models.Index(fields=["user", "type"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_type_display()} - {self.amount}"
