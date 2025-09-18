from rest_framework import serializers
from .models import Dialog, Message, Media
class MediaSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Media
        fields = ["id", "media_type", "file", "url"]

    def get_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None
class MessageSerializer(serializers.ModelSerializer):
    media = MediaSerializer(many=True,read_only = True)

    def create(self, validated_data):
        media_files = validated_data.pop("media_files", [])
        # сначала создаём само сообщение
        message = Message.objects.create(**validated_data)
        # потом уже добавляем файлы в M2M
        for media in media_files:
            message.media_files.add(media)
        return message
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
