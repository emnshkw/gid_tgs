from django.urls import path
from .views import AccountByUserIDView, AdsByAccountUserIDView, AvitoAdCreateView,UpdateAdView

urlpatterns = [
    path('account/<str:user_id>/', AccountByUserIDView.as_view(), name='account-by-user-id'),
    path('ads/add/', AvitoAdCreateView.as_view(), name='ad-create'),
    path('ads/update/<str:ad_id>/', UpdateAdView.as_view(), name='ad-update'),
    path('ads/get/<str:user_id>/', AdsByAccountUserIDView.as_view(), name='ads-by-user-id'),

]
