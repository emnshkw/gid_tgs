from django.db import models


class YaAccountModel(models.Model):
    name = models.TextField("Фамилия Имя",default='',unique=True)
    categories = models.TextField("Выбранные категории",blank=True,null=True)
    city = models.TextField("Город",default='')
    new_cats = models.TextField("Категории, которые нужно добавить",blank=True,null=True)
    del_cats = models.TextField("Категории, которые нужно удалить",blank=True,null=True)
    new_city = models.TextField('Новый город',blank=True,null=True)
    need_update = models.BooleanField("Есть изменения, программе нужно отработать",default=True)


    def __str__(self):
        need_update = 'Программа вносит изменения' if self.new_cats != '' or self.del_cats != '' or self.new_city != '' else "Аккаунт заполнен"
        new_cats_len = len([i for i in self.new_cats.replace("\r","").split("\n") if i != ''])
        del_cats_len = len([i for i in self.del_cats.replace("\r","").split("\n") if i != ''])
        self.need_update = need_update
        self.save()
        return f'{self.name}. {need_update}. {new_cats_len} категорий нужно добавить, {del_cats_len} категорий нужно удалить.'


    class Meta:
        verbose_name = 'Яндекс Аккаунт'
        verbose_name_plural = 'Яндекс Аккаунты'