from django.urls import path
from .views import StartAuthView, CompleteAuthView

urlpatterns = [
    path('start/', StartAuthView.as_view(), name='start_auth'),
    path('complete/', CompleteAuthView.as_view(), name='complete_auth'),
]
