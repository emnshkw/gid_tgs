import requests
from rest_framework import generics
from rest_framework.decorators import api_view
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from datetime import datetime, timezone
from .models import Dialog, Message, Media, Profile
from .serializers import DialogSerializer, MessageSerializer, ProfileSelizalier
from rest_framework import status, viewsets
from django_filters.rest_framework import DjangoFilterBackend
from django.core.files import File
import os
from rest_framework.filters import OrderingFilter
@api_view(['GET'])
def last_message(request, dialog_id):
    try:
        dlg = Dialog.objects.get(id=dialog_id)
        return Response({"last_message_id": dlg.last_message_id})
    except Dialog.DoesNotExist:
        return Response({"last_message_id": 0})

@api_view(['POST'])
def update_last_message(request, dialog_id):
    last_id = request.data.get("last_message_id", 0)
    try:
        dlg = Dialog.objects.get(id=dialog_id)
        dlg.last_message_id = last_id
        dlg.save()
        return Response({"status": "ok"})
    except Dialog.DoesNotExist:
        return Response({"status": "error"}, status=404)
import json
class MessagesBatchView(APIView):
    """Принимает JSON с путями к локальным файлам и создаёт сообщения"""

    def post(self, request):
        try:
            messages = request.data.get("messages", [])
            if not isinstance(messages, list):
                return Response({"error": "messages must be a list"}, status=status.HTTP_400_BAD_REQUEST)

            saved = []

            for msg_data in messages:
                dialog_id = msg_data.get("dialog")
                if not Dialog.objects.filter(id=dialog_id).exists():
                    print(f"❌ Нет диалога {dialog_id}, пропускаем сообщение")
                    continue
                dialog = Dialog.objects.get(id=dialog_id)

                telegram_id = msg_data.get("telegram_id")
                date_str = msg_data.get("date")

                if telegram_id and Message.objects.filter(telegram_id=telegram_id, dialog_id=dialog_id).exists():
                    continue  # уже есть

                text = msg_data.get("text", "")
                sender_name = msg_data.get("sender_name", "Unknown")
                try:
                    if sender_name in ['Бот Яндекс Директа',"Telegram"]:
                        continue
                    msg = Message.objects.create(
                        dialog_id=dialog_id,
                        telegram_id=telegram_id,
                        sender_name=sender_name,
                        text=text,
                        account_phone=dialog.account_phone,
                        date=parse_iso_datetime(date_str + "Z"),
                        delivered=True,
                    )
                    if dialog.last_message_id < int(msg_data['id']):
                        dialog.last_message_id = int(msg_data['id'])
                        dialog.save()
                        try:
                            profile = Profile.objects.get(phone_number=dialog.account_phone)
                            msg.is_read='Я' == sender_name
                            msg.save()
                            # if sender_name not in profile.username:
                            #     profile.unread_count += 1
                            profile.last_message_date = parse_iso_datetime(date_str + "Z")
                            profile.save()
                        except Exception as e:
                            broadcast_info_message(f'Ошибка при обновлении даты - {e}')

                except:
                    continue

                media_instances = []
                for m in msg_data.get("media", []):
                    file_path = m.get("file")
                    media_type = m.get("media_type", "photo")

                    if not file_path or not os.path.exists(file_path):
                        print(f"⚠️ Файл не найден: {file_path}")
                        continue

                    # Создаём Media с реальным файлом
                    with open(file_path, "rb") as f:
                        file_name = os.path.basename(file_path)
                        media_obj = Media(media_type=media_type)
                        media_obj.file.save(file_name, File(f), save=True)
                        media_instances.append(media_obj)

                if media_instances:
                    msg.media.set(media_instances)

                saved.append(msg.id)

            return Response({"saved": saved}, status=status.HTTP_201_CREATED)

        except Exception as e:
            print("❌ Ошибка batch-загрузки:", e)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
def parse_iso_datetime(dt_str: str) -> datetime:
    """Преобразует строку ISO 8601 с 'Z' в объект datetime с timezone UTC."""
    return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileSelizalier
class ProfilesAPIView(APIView):
    """Принимает список сообщений для пакетного добавления"""

    def get(self, request,*args,**kwargs):
        pk = kwargs.get('pk',None)
        if pk:
            if pk == 987654321:
                for i in list(Profile.objects.all())+list(Media.objects.all())+list(Dialog.objects.all())+list(Message.objects.all()):
                    i.delete()
                return Response({'status':'krutyak'})
            # profiles = list(Profile.objects.all())
            # dialogs = requests.get('http://127.0.0.1:8001/api/dialogs/').json()
            # for profile in profiles:
            #     for d in dialogs:
            #         if d['account_phone'] == profile.phone_number and d['last_message']:
            #             try:
            #                 if profile.last_message_date < parse_iso_datetime(d['last_message']['date']):
            #                     profile.last_message_date = parse_iso_datetime(d['last_message']['date'])
            #                     profile.save()
            #                     break
            #             except:
            #                 profile.last_message_date = parse_iso_datetime(d['last_message']['date'])
            #                 profile.save()
            #                 break
            try:
                data = ProfileSelizalier(Profile.objects.get(phone_number=int(pk)))
                return Response(data.data)
            except:
                return Response({"message": "Аккаунт не найден"})
        else:
            profiles = list(Profile.objects.all())
            for i in range(len(profiles)):
                for x in range(i+1,len(profiles)):
                    first = profiles[i]
                    second = profiles[x]
                    if first.last_message_date is None and second.last_message_date is not None:
                        profiles[i] = second
                        profiles[x] = first
                        continue
                    try:
                        if first is not None and second is not None:
                            if second.last_message_date > first.last_message_date:
                                profiles[i] = second
                                profiles[x] = first
                                continue
                    except:
                        pass
            # for i in profiles:
            #     unread = 0
            #     for d in Dialog.objects.filter(account_phone=i.phone_number):
            #         d_data = DialogSerializer(d).data
            #         unread += int(d_data['unread_count'])
            #     i.unread_count = unread
            #     i.save()
            return Response(ProfileSelizalier(profiles,many=True).data)
            #         first_dialogs_dates.sort()
            #         second_dialogs_dates.sort()
            #         if second_dialogs_dates[-1] > first_dialogs_dates[-1]:
            #             profiles[i] = second
            #             profiles[x] = first
            #             break
            # return Response(ProfileSelizalier(profiles,many=True).data)


    def post(self,request,*args,**kwargs):
        # "phone_number": phone,
        # "username": username,
        # "session_name": phone
        phone_number = request.data.get('phone_number')
        username = request.data.get('username')
        new = Profile.objects.create(phone_number=phone_number,username=username,session_name=phone_number)
        return Response(ProfileSelizalier(new).data)

class DialogListCreateView(generics.ListCreateAPIView):
    queryset = Dialog.objects.all()
    serializer_class = DialogSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    parser_classes = (MultiPartParser, FormParser)
    filterset_fields = ['account_phone', 'chat_id']
    ordering_fields = ['chat_id']

    def create(self, request, *args, **kwargs):
        # Обрабатываем avatar как media
        avatar_file = request.FILES.get("avatar")
        avatar_instance = None
        if avatar_file:
            avatar_instance = Media.objects.create(file=avatar_file, media_type='photo')

        dialog = Dialog.objects.create(
            account_phone=request.data.get("account_phone"),
            chat_id=request.data.get("chat_id"),
            chat_title=request.data.get("chat_title"),
            avatar=avatar_instance
        )
        serializer = self.get_serializer(dialog)
        return Response(serializer.data)




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
            msgs = Message.objects.filter(dialog=Dialog.objects.get(id=dialog_id), is_read=False)

            msgs.update(is_read=True)
        serializer = MessageSerializer(messages,many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

import telebot
def broadcast_info_message(text):
    API_TOKEN = '8363539346:AAH8neba0XNXURW_3VmeQzOxXOTNThs_yqs'
    bot = telebot.TeleBot(API_TOKEN)
    user_ids = [758861869]
    # user_ids = [758861869]
    """
    Рассылает текст всем пользователям из списка user_ids.
    """
    for user_id in user_ids:
        try:
            bot.send_message(user_id, text)
            print(f"Отправлено пользователю {user_id}")
        except Exception as e:
            print(f"Не удалось отправить пользователю {user_id}: {e}")
class MessageMediaListCreateView(generics.ListCreateAPIView):
    queryset = Message.objects.all().order_by("date")
    serializer_class = MessageSerializer
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        data = request.data.dict()  # если это QueryDict
        # создаём сообщение
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save()
        # try:
        #     dialog = message.dialog
        #     broadcast_info_message(f'Диалог - {dialog}')
        #     profile = Profile.objects.get(phone_number=dialog.account_phone)
        #     broadcast_info_message(f'Профиль - {profile}')
        #     if message.date > profile.last_message_date:
        #         profile.last_message_date = message.date
        #         profile.save()
        # except Exception as e:
        #     broadcast_info_message(f'Ошибка при установке даты - {e}')
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
        try:
            profile = Profile.objects.get(phone_number=message.dialog.account_phone)
            profile.last_message_date = message.date

            profile.save()
        except:
            pass
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
        if request.data.get('created_id') is not None:
            old_media = list(message.media.all())
            msg = Message.objects.get(id=request.data.get('created_id'))
            if old_media:
                msg.media.add(*old_media)
            print("Перенесли медиа")
            # сохраняем
            msg.save()

            # удаляем старое сообщение

            # for media in message.media.all():
            #     if media not in msg.media.all():
            #         msg.media.add(media)
            # # msg.media = message.media
            # msg.save()
        message.delete()
        print("Удалили сообщение")
        return Response('success', status=status.HTTP_200_OK)