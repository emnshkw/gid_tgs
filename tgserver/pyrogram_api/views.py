API_ID = 9018428  # 🔹 Твой api_id от https://my.telegram.org
API_HASH = "93732d8d7cd181e163b69ad5079d2020"  # 🔹 Твой api_hash
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from .serializers import StartAuthSerializer, CompleteAuthSerializer


executor = ThreadPoolExecutor(max_workers=4)
active_sessions = {}

def run_in_thread(coro_func, *args, **kwargs):
    """Запускает корутину Pyrogram в отдельном event loop внутри пула потоков."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro_func(*args, **kwargs))


class StartAuthView(APIView):
    def post(self, request):
        serializer = StartAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        session_path = serializer.validated_data["session_path"]

        async def send_code():
            async with Client(session_path, api_id=API_ID, api_hash=API_HASH) as app:
                sent = await app.send_code(phone)
                return sent.phone_code_hash

        try:
            phone_code_hash = executor.submit(run_in_thread, send_code).result()
            # сохраняем только hash, а не сам клиент
            active_sessions[phone] = {"phone_code_hash": phone_code_hash, "session_path": session_path}
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

        session_path = active_sessions[phone]["session_path"]
        phone_code_hash = active_sessions[phone]["phone_code_hash"]

        async def complete_login():
            async with Client(session_path, api_id=API_ID, api_hash=API_HASH) as app:
                await app.sign_in(phone_number=phone, phone_code_hash=phone_code_hash, phone_code=code)
                return True

        try:
            executor.submit(run_in_thread, complete_login).result()
            del active_sessions[phone]
            return Response({"status": "authorized", "session_saved": session_path})
        except SessionPasswordNeeded:
            return Response({"error": "2FA password required"}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
