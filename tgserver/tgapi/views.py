from rest_framework import generics
from rest_framework.response import Response
from .models import Dialog, Message
from .serializers import DialogSerializer, MessageSerializer
from rest_framework import status
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


class MessageUpdateDeliveredView(generics.UpdateAPIView):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer

    def patch(self, request, *args, **kwargs):
        message = self.get_object()
        delivered = request.data.get("delivered")
        print(message)
        print(delivered)
        if delivered is not None:
            message.delivered = delivered
            message.save()
        serializer = MessageSerializer(message)
        return Response(serializer.data, status=status.HTTP_200_OK)
