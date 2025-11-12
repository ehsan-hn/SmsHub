from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    rate_limit_per_minute = models.PositiveIntegerField(default=2000)
    balance = models.BigIntegerField(default=0)
