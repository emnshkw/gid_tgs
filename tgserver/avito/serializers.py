from rest_framework import serializers
from .models import AvitoAccount, AvitoAd


class AvitoAdSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvitoAd
        fields = '__all__'


class AvitoAccountSerializer(serializers.ModelSerializer):
    ads = AvitoAdSerializer(many=True, read_only=True)

    class Meta:
        model = AvitoAccount
        fields = '__all__'
