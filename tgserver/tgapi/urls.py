from django.urls import path
from .views import DialogListCreateView, MessageListCreateView, MessageUpdateDeliveredView,MessageViewSet

urlpatterns = [
    path('api/dialogs/', DialogListCreateView.as_view()),
    path('api/dialogs/<int:pk>/', DialogListCreateView.as_view()),
    path('api/messages/', MessageListCreateView.as_view()),
    path('api/messages_media/', MessageViewSet),
    path('api/messages/<int:pk>/', MessageUpdateDeliveredView.as_view()),
]
