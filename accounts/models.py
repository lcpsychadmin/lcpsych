from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
import uuid


class EmailConfirmation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_confirmations")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(blank=True, null=True)

    @staticmethod
    def generate_token() -> str:
        return uuid.uuid4().hex

    def __str__(self) -> str:
        return f"EmailConfirmation({self.user_id})"
