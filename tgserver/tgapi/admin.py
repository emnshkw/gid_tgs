from django.contrib import admin
from .models import Dialog, Message
from django.contrib.auth.models import Group
admin.site.unregister(Group)

admin.site.register(Dialog)
admin.site.register(Message)