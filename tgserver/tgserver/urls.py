"""
URL configuration for tgserver project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import re_path
from django.urls import path, include
from django.conf.urls.static import static,serve
from django.conf import settings
import os
from ya_accounts_info.views import YaAccountAPIView
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLUTTER_WEB_APP = os.path.join(BASE_DIR, 'landing')
from tgapi.views import DialogListCreateView, MessageListCreateView, MessageUpdateDeliveredView,MessageMediaListCreateView, ProfileViewSet,MessagesBatchView,ProfilesAPIView,last_message,update_last_message
from django.contrib import admin
from django.urls import path, include
from avito.views import AccountByUserIDView,AdsByAccountUserIDView,AvitoAdCreateView

def flutter_serve(request, path=''):
    if path == '' or path.endswith('/'):
        path = 'index.html'
    return serve(request, path, document_root=FLUTTER_WEB_APP)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('avito/', include('avito_app.urls')),
                  path('api/dialogs/<int:dialog_id>/last_message/', last_message, name='dialog-last-message'),
                  path('api/dialogs/<int:dialog_id>/last_message/update/', update_last_message,
                       name='dialog-update-last-message'),
    path('ya_account/',YaAccountAPIView.as_view()),
    path('api/profiles/',ProfilesAPIView.as_view()),
    path('api/profiles/<int:pk>/',ProfilesAPIView.as_view()),
    path('api/dialogs/', DialogListCreateView.as_view()),
    path('api/dialogs/<int:pk>/', DialogListCreateView.as_view()),
    path('api/messages/', MessageListCreateView.as_view()),
    path('api/messages_media/', MessageMediaListCreateView.as_view()),
    path('api/messages/<int:pk>/', MessageUpdateDeliveredView.as_view()),
path("api/messages_batch/", MessagesBatchView.as_view(), name="messages_batch"),

                  path('pyrogram_api/', include('pyrogram_api.urls')),
    path('', include('tgapi.urls')),
                  path('telegram/', flutter_serve),
                  re_path(r'^telegram/(?P<path>.*)$', flutter_serve),

              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = 'Панель администрирования GID'
admin.site.index_title = 'GID'