from django.db import models


class TelegramAuth(models.Model):
    phone = models.CharField(max_length=32, unique=True)
    session_path = models.CharField(max_length=255)
    phone_code_hash = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(
        max_length=32,
        choices=[
            ("created", "Created"),
            ("code_sent", "Code Sent"),
            ("authorized", "Authorized"),
            ("2fa_required", "2FA Required"),
            ("error", "Error"),
        ],
        default="created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.phone} ({self.status})"
