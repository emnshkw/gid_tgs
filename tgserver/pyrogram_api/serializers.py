from rest_framework import serializers


class StartAuthSerializer(serializers.Serializer):
    phone = serializers.CharField()
    session_path = serializers.CharField()


class CompleteAuthSerializer(serializers.Serializer):
    phone = serializers.CharField()
    code = serializers.CharField()
