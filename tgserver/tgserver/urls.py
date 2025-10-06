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


def flutter_serve(request, path=''):
    if path == '' or path.endswith('/'):
        path = 'index.html'
    return serve(request, path, document_root=FLUTTER_WEB_APP)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('ya_account/',YaAccountAPIView.as_view()),
    path('', include('tgapi.urls')),
                  path('', flutter_serve),
                  re_path(r'^(?P<path>.*)$', flutter_serve),

              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = 'Панель администрирования GID'
admin.site.index_title = 'GID'