from django.db import models
class Media(models.Model):
    file = models.CharField(max_length=10000)
    media_type = models.CharField(
        max_length=10000,
        choices=[
            ("photo", "Фото"),
            ("video", "Видео"),
            ("voice", "Голос"),
            ("document", "Документ"),
        ],
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
class Dialog(models.Model):
    account_phone = models.CharField(max_length=50)
    chat_id = models.BigIntegerField()
    avatar = models.ForeignKey(Media, null=True, blank=True, on_delete=models.SET_NULL)
    chat_title = models.CharField(max_length=255)
    last_message_id = models.BigIntegerField(default=0)

    class Meta:
        verbose_name = 'Диалог'
        verbose_name_plural = "Диалоги"
        unique_together = ("account_phone", "chat_id")

    def __str__(self):
        return f"{self.account_phone} - {self.chat_title}. {self.avatar}"


class Message(models.Model):
    dialog = models.ForeignKey(Dialog, on_delete=models.CASCADE)
    telegram_id = models.BigIntegerField(null=True, blank=True)
    sender_name = models.CharField(max_length=255)
    text = models.TextField(blank=True)
    media_file = models.CharField(max_length=1024, blank=True,null=True)
    media_type = models.CharField(max_length=50, blank=True,null=True)
    delivered = models.BooleanField(default=False)
    account_phone = models.CharField(max_length=20, blank=True,null=True)
    date = models.DateTimeField()
    is_read = models.BooleanField(default=False)
    media = models.ManyToManyField("Media", related_name="messages", blank=True)
    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        unique_together = ("dialog", "text", "date")
        ordering = ["date"]  # сортировка по дате

    def __str__(self):
        return f"{self.sender_name}: {self.text[:30]}"
class Profile(models.Model):
    phone_number = models.CharField(max_length=20, unique=True)
    session_name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    username = models.CharField(max_length=255, blank=True, null=True)
    last_message_date = models.DateTimeField(blank=True,null=True)
    unread_count = models.IntegerField(default=0)

    def __str__(self):
        return f"Подключенный аккаунт - {self.phone_number} ({self.session_name})"


    class Meta:
        verbose_name = 'ТГ Аккаунт'
        verbose_name_plural = 'ТГ Аккаунты'
