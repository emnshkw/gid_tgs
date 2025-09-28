from django.db import models


class YaAccountModel(models.Model):
    name = models.TextField("Фамилия Имя",default='')
    categories = models.TextField("Выбранные категории",blank=True,null=True)
    city = models.TextField("Город",default='')
    new_cats = models.TextField("Категории, которые нужно добавить",blank=True,null=True)
    del_cats = models.TextField("Категории, которые нужно удалить",blank=True,null=True)
    new_city = models.TextField('Новый город',blank=True,null=True)
    need_update = models.BooleanField("Есть изменения, программе нужно отработать",default=True)


    def __str__(self):
        need_update = 'Программа вносит изменения' if self.need_update else "Аккаунт заполнен"
        return f'{self.name}. {need_update}'


    class Meta:
        verbose_name = 'Яндекс Аккаунт'
        verbose_name_plural = 'Яндекс Аккаунты'