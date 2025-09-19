from rest_framework import generics
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from .models import Dialog, Message, Media
from .serializers import DialogSerializer, MessageSerializer
from rest_framework import status, viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

class DialogListCreateView(generics.ListCreateAPIView):
    queryset = Dialog.objects.all()
    serializer_class = DialogSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['account_phone', 'chat_id']
    ordering_fields = ['chat_id']


class MessageListCreateView(generics.ListCreateAPIView):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['dialog', 'delivered', 'telegram_id']
    ordering_fields = ['date']
    def get(self,request,*args,**kwargs):
        dialog_id = request.GET.get('dialog', None)
        messages = Message.objects.all()
        telegram_id = request.GET.get('telegram_id', None)
        delivered = request.GET.get('delivered', None)
        from_gui = request.GET.get('from_gui',None)
        if dialog_id is not None:
            dialog_id = int(dialog_id.replace("'",'').replace('/',''))
            messages = messages.filter(dialog=Dialog.objects.get(id=dialog_id))

        # 👇 отмечаем все сообщения в этом диалоге как прочита

        if delivered is not None:
            delivered = bool(delivered.replace("'",'').replace('/',''))
            serializer = MessageSerializer(Message.objects.filter(delivered=False), many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        if telegram_id is not None:
            telegram_id = int(telegram_id.replace("'", '').replace('/', ''))
            messages = messages.filter(telegram_id=telegram_id)
        if dialog_id is not None and telegram_id is None and from_gui is not None:
            Message.objects.filter(dialog=Dialog.objects.get(id=dialog_id), is_read=False).update(is_read=True)
        serializer = MessageSerializer(messages,many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
class MessageMediaListCreateView(generics.ListCreateAPIView):
    queryset = Message.objects.all().order_by("date")
    serializer_class = MessageSerializer
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        data = request.data.copy()

        # создаём сообщение
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save()

        # прикрепляем файлы, если есть
        files = request.FILES.getlist("files")
        print(len(files))
        for f in files:
            ext = f.name.split(".")[-1].lower()
            if ext in ["jpg", "jpeg", "png"]:
                mtype = "photo"
            elif ext in ["mp4"]:
                mtype = "video"
            elif ext in ["ogg"]:
                mtype = "voice"
            else:
                mtype = "document"

            media = Media.objects.create(file=f, media_type=mtype)
            message.media.add(media)

        message.save()
        return Response(self.get_serializer(message).data, status=status.HTTP_201_CREATED)

class MessageUpdateDeliveredView(generics.UpdateAPIView):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer


    def patch(self, request, *args, **kwargs):
        message = self.get_object()
        delivered = request.data.get("delivered")
        if delivered is not None:
            message.delivered = delivered
            message.save()
        serializer = MessageSerializer(message)
        return Response(serializer.data, status=status.HTTP_200_OK)
    def delete(self, request, *args, **kwargs):

        message = self.get_object()
        if request.data.get('created') is not None:
            old_media = list(message.media.all())
            msg = Message.objects.get(id=request.data.get('created')['id'])
            if old_media:
                msg.media.add(*old_media)

            # сохраняем
            msg.save()

            # удаляем старое сообщение

            # for media in message.media.all():
            #     if media not in msg.media.all():
            #         msg.media.add(media)
            # # msg.media = message.media
            # msg.save()
        message.delete()
        serializer = MessageSerializer(message)
        return Response(serializer.data, status=status.HTTP_200_OK)