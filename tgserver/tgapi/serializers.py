from rest_framework import serializers
from .models import Dialog, Message

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'

class DialogSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Dialog
        fields = '__all__'
        extra_fields = ["last_message"]

    def get_last_message(self, obj):
        last_msg = Message.objects.filter(dialog=obj).order_by("-date").first()
        if last_msg:
            return MessageSerializer(last_msg).data
        return None

    def get_unread_count(self, obj):
        return Message.objects.filter(dialog=obj,is_read=False).count()
class DialogCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dialog
        fields = '__all__'
