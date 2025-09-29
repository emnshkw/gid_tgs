from django.contrib import admin
from .models import YaAccountModel


# ----- Actions -----
@admin.action(description="Пометить как требующие обновления")
def mark_need_update(modeladmin, request, queryset):
    queryset.update(need_update=True)


@admin.action(description="Снять пометку об обновлении")
def unmark_need_update(modeladmin, request, queryset):
    queryset.update(need_update=False)


# ----- Admin -----
@admin.register(YaAccountModel)
class YaAccountAdmin(admin.ModelAdmin):
    # list_display = ("name", "city", "need_update")
    list_filter = ("need_update", "city")
    search_fields = ("name", "city")

    actions = [mark_need_update, unmark_need_update]