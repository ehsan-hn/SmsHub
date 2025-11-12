from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class SMSStatus(models.TextChoices):
    CREATED = "created", "ساخته شده"
    IN_QUEUE = "in_queue", "در صف ارسال"
    SENT = "sent", "ارسال شده"
    DELIVERED = "delivered", "تحویل شده"
    FAILED = "failed", "خطا در ارسال"
    USER_CANCELLED = "user_canceled", "کاربر لغو کرده"
    USER_BLOCKED = "user_blocked", "کاربر بلاک کرده"


class SMS(models.Model):
    message_id = models.IntegerField(unique=True, null=True, db_index=True)
    user = models.ForeignKey(
        User,
        verbose_name="کاربر",
        on_delete=models.CASCADE,
        related_name="sms_messages",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")
    modified_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ آخرین تغییر")
    last_attempt_at = models.DateTimeField(verbose_name="تاریخ آخرین تلاش", null=True, blank=True)
    attempts_num = models.PositiveIntegerField(default=0, verbose_name="تعداد تلاش‌ها")
    service_error = models.TextField(verbose_name="خطای سرویس", blank=True)
    status = models.CharField(
        max_length=255,
        verbose_name="وضعیت",
        choices=SMSStatus.choices,
        default=SMSStatus.CREATED,
    )
    sender = models.CharField(max_length=255, verbose_name="شماره فرستنده")
    receiver = models.CharField(max_length=255, verbose_name="شماره گیرنده")
    content = models.TextField(verbose_name="محتوای پیام")
    cost = models.BigIntegerField(verbose_name="هزینه (ریال)")
    is_express = models.BooleanField(default=False, verbose_name="اکسپرس")

    class Meta:
        ordering = ["-created_at"]
        db_table = "SMS"
        verbose_name = "پیامک"
        verbose_name_plural = "پیامک‌ها"
        indexes = [
            models.Index(fields=["user"], name="sms_user_idx"),
            models.Index(fields=["user", "status"], name="sms_user_status_idx"),
            models.Index(fields=["user", "created_at"], name="sms_user_created_at_idx"),
            models.Index(fields=["receiver"], name="sms_receiver_idx"),
        ]

    def __str__(self):
        return f"SMS {self.message_id} to {self.receiver} ({self.status})"
