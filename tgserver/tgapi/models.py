from django.db import models

class Dialog(models.Model):
    account_phone = models.CharField(max_length=50)
    chat_id = models.BigIntegerField()
    chat_title = models.CharField(max_length=255)

    class Meta:
        verbose_name = 'Диалог'
        verbose_name_plural = "Диалоги"
        unique_together = ("account_phone", "chat_id")

    def __str__(self):
        return f"{self.account_phone} - {self.chat_title}"


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

    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        unique_together = ("dialog", "text", "date")
        ordering = ["date"]  # сортировка по дате

    def __str__(self):
        return f"{self.sender_name}: {self.text[:30]}"
