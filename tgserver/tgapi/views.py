from rest_framework import generics
from rest_framework.response import Response
from .models import Dialog, Message
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
        if dialog_id is not None:
            dialog_id = int(dialog_id)
        print(dialog_id)
        print(len(Message.objects.filter(dialog=Dialog.objects.get(id=dialog_id),is_read=False)))
        qs = Message.objects.filter(dialog=Dialog.objects.get(id=dialog_id),is_read=False).update(is_read=True)

        # 👇 отмечаем все сообщения в этом диалоге как прочитанные
        qs.filter(is_read=False).update(is_read=True)

        serializer = MessageSerializer(Message.objects.get(dialog=Dialog.objects.get(id=dialog_id)))
        return Response(serializer.data, status=status.HTTP_200_OK)
class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer


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
        message.delete()
        serializer = MessageSerializer(message)
        return Response(serializer.data, status=status.HTTP_200_OK)