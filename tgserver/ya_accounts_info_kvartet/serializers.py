from rest_framework import serializers
from .models import YaAccountKvartetModel


class YaAccountKvartetSelizalier(serializers.ModelSerializer):
    class Meta:
        model = YaAccountKvartetModel
        fields = '__all__'