from rest_framework import serializers
from .models import Dialog, Message

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'

class DialogSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Dialog
        fields = '__all__'
        extra_fields = ["last_message"]

    def get_last_message(self, obj):
        last_msg = obj.messages.order_by("-date").first()
        if last_msg:
            return MessageSerializer(last_msg).data
        return None
class DialogCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dialog
        fields = '__all__'
