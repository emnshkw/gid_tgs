from django.urls import path
from .views import DialogListCreateView, MessageListCreateView, MessageUpdateDeliveredView,MessageMediaListCreateView, ProfileViewSet,MessagesBatchView
from rest_framework.routers import DefaultRouter
router = DefaultRouter()
router.register(r'api/profiles', ProfileViewSet)
urlpatterns = [
    path('api/profiles',ProfilesAPIView.as_view()),
    path('api/dialogs/', DialogListCreateView.as_view()),
    path('api/dialogs/<int:pk>/', DialogListCreateView.as_view()),
    path('api/messages/', MessageListCreateView.as_view()),
    path('api/messages_media/', MessageMediaListCreateView.as_view()),
    path('api/messages/<int:pk>/', MessageUpdateDeliveredView.as_view()),
path("api/messages_batch/", MessagesBatchView.as_view(), name="messages_batch"),
] + router.urls