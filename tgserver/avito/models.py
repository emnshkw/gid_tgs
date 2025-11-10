from django.db import models


class AvitoAccount(models.Model):
    """Модель аккаунта Авито."""
    phone_number = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    user_id = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return f"{self.name} ({self.phone_number})"

    class Meta:
        verbose_name = 'Авито аккаунт'
        verbose_name_plural = 'Авито аккаунты'
class AvitoAd(models.Model):
    """Модель объявления Авито."""
    ad_id = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=255)
    position = models.IntegerField()
    view_price = models.DecimalField(max_digits=10, decimal_places=2)
    link = models.URLField(max_length=500)  # 👈 новое поле — ссылка на объявление
    account = models.ForeignKey(AvitoAccount, related_name='ads', on_delete=models.CASCADE)
    update_date = models.DateTimeField('Дата обновления позиции',auto_now=False,null=True)
    updated_after_position = models.BooleanField('После обновления позиции обновлена ставка',default=False)
    def __str__(self):
        return f"{self.title} (Аккаунт: {self.account.name}). Позиция - {self.position}, ставка - {self.view_price}"


    class Meta:
        verbose_name = 'Авито объявление'
        verbose_name_plural = 'Авито объявления'