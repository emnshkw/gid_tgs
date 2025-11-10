from django.contrib import admin
from .models import AvitoAd,AvitoAccount

# ----- Admin -----
@admin.register(AvitoAd)
class AvidoAdAdmin(admin.ModelAdmin):
    # list_display = ("name", "city", "need_update")
    list_filter = ("updated_after_position",)
    search_fields = ("title",)
    actions = []
# admin.site.register(AvitoAd)
admin.site.register(AvitoAccount)