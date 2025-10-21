from django.urls import path
from .views import UploadSessionView

urlpatterns = [
    path('send/', UploadSessionView.as_view(), name='start_auth')
]
