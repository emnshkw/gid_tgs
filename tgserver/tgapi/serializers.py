from rest_framework import serializers
from .models import Dialog, Message

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'

class DialogSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Dialog
        fields = '__all__'
class DialogCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dialog
        fields = '__all__'
