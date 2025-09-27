from rest_framework import serializers
from .models import YaAccountModel


class YaAccountSelizalier(serializers.ModelSerializer):
    class Meta:
        model = YaAccountModel
        fields = '__all__'