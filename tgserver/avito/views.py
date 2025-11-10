from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import AvitoAccount, AvitoAd
from .serializers import AvitoAccountSerializer, AvitoAdSerializer


class AccountByUserIDView(APIView):
    """
    GET /api/account/<user_id>/
    Возвращает данные аккаунта по user_id.
    """
    def get(self, request, user_id):
        account = get_object_or_404(AvitoAccount, user_id=user_id)
        serializer = AvitoAccountSerializer(account)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdsByAccountUserIDView(APIView):
    """
    GET /api/ads/<user_id>/
    Возвращает все объявления, принадлежащие аккаунту с данным user_id.
    """
    def get(self, request, user_id):
        ads = AvitoAd.objects.filter(account__user_id=user_id)
        serializer = AvitoAdSerializer(ads, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AvitoAdCreateView(APIView):
    """
    POST /api/ads/add/
    Добавляет новое объявление.

    Пример тела запроса:
    {
        "ad_id": "A001",
        "title": "Продам телефон",
        "position": 1,
        "view_price": 15.50,
        "link": "https://www.avito.ru/item/12345",
        "account": 1
    }
    """
    def post(self, request):
        serializer = AvitoAdSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Объявление успешно добавлено", "data": serializer.data},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
from datetime import datetime,timedelta
class UpdateAdView(APIView):
    """
    PATCH /avito/ads/update/<ad_id>/

    Обновляет цену и/или позицию объявления.

    Пример тела запроса:
    {
        "position": 2,
        "view_price": 18.50
    }
    """

    def patch(self, request, ad_id):
        ad = get_object_or_404(AvitoAd, ad_id=ad_id)

        allowed_fields = ["position", "view_price"]
        data = {k: v for k, v in request.data.items() if k in allowed_fields}
        data['update_date'] = datetime.now()+timedelta(hours=3)
        data['updated_after_position'] = False
        if not data:
            return Response(
                {"error": "Укажите хотя бы одно поле: position или view_price"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AvitoAdSerializer(ad, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Объявление обновлено", "data": serializer.data},
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UpdateAdViewPriceView(APIView):
    """
    PATCH /avito/ads/update/<ad_id>/

    Обновляет цену и/или позицию объявления.

    Пример тела запроса:
    {
        "position": 2,
        "view_price": 18.50
    }
    """

    def patch(self, request, ad_id):
        ad = get_object_or_404(AvitoAd, ad_id=ad_id)

        allowed_fields = ["view_price"]
        data = {k: v for k, v in request.data.items() if k in allowed_fields}
        # data['update_date'] = datetime.now() + timedelta(hours=3)
        data['updated_after_position'] = True
        if not data:
            return Response(
                {"error": "Укажите хотя бы одно поле: position или view_price"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AvitoAdSerializer(ad, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Объявление обновлено", "data": serializer.data},
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeleteAdView(APIView):
    """
    DELETE /api/ads/<ad_id>/
    Удаляет объявление по его ad_id.
    """
    def delete(self, request, ad_id):
        ad = get_object_or_404(AvitoAd, ad_id=ad_id)
        ad.delete()
        return Response({"message": "Объявление удалено"}, status=status.HTTP_204_NO_CONTENT)
