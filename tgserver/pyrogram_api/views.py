import asyncio
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from .serializers import StartAuthSerializer, CompleteAuthSerializer

active_sessions = {}
API_ID = 9018428  # 🔹 Твой api_id от https://my.telegram.org
API_HASH = "93732d8d7cd181e163b69ad5079d2020"  # 🔹 Твой api_hash

def ensure_event_loop():
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)


class StartAuthView(APIView):
    def post(self, request):
        serializer = StartAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        session_path = serializer.validated_data["session_path"]

        ensure_event_loop()  # 👈 добавили эту строку

        client = Client(session_path, api_id=API_ID, api_hash=API_HASH)

        try:
            client.connect()
            sent = client.send_code(phone)
            active_sessions[phone] = {"client": client, "phone_code_hash": sent.phone_code_hash, "session_path": session_path}
            return Response({"status": "code_sent"})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CompleteAuthView(APIView):
    def post(self, request):
        serializer = CompleteAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        code = serializer.validated_data["code"]

        if phone not in active_sessions:
            return Response({"error": "Session not found"}, status=status.HTTP_400_BAD_REQUEST)

        ensure_event_loop()  # 👈 тоже добавили

        session = active_sessions[phone]
        client = session["client"]
        phone_code_hash = session["phone_code_hash"]

        try:
            client.sign_in(phone_number=phone, phone_code_hash=phone_code_hash, phone_code=code)
            client.disconnect()
            del active_sessions[phone]
            return Response({"status": "authorized", "session_saved": session["session_path"]})
        except SessionPasswordNeeded:
            return Response({"error": "2FA password required"}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
