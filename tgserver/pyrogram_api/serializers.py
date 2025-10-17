from rest_framework import serializers

class StartAuthSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    session_path = serializers.CharField(max_length=255)

class CompleteAuthSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=10)
    session_path = serializers.CharField(max_length=255)
