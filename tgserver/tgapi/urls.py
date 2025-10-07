from django.urls import path
from .views import DialogListCreateView, MessageListCreateView, MessageUpdateDeliveredView,MessageMediaListCreateView, ProfileViewSet,MessagesBatchView,ProfilesAPIView
from rest_framework.routers import DefaultRouter
router = DefaultRouter()
# router.register(r'api/profiles', ProfileViewSet)
urlpatterns = []