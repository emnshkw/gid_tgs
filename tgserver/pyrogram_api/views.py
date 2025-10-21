API_ID = 9018428  # 🔹 Твой api_id от https://my.telegram.org
API_HASH = "93732d8d7cd181e163b69ad5079d2020"  # 🔹 Твой api_hash
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pyrogram import Client
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import TelegramAuth
from .serializers import StartAuthSerializer,CompleteAuthSerializer


executor = ThreadPoolExecutor(max_workers=5)


def run_in_thread(coro_func, *args, **kwargs):
    """Запускает Pyrogram-корутину в отдельном event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro_func(*args, **kwargs))


class StartAuthView(APIView):
    """
    POST /api/start/
    {
      "phone": "+79998887766",
      "session_path": "sessions/test.session"
    }
    """

    def post(self, request):
        serializer = StartAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        session_path = serializer.validated_data["session_path"]

        auth, _ = TelegramAuth.objects.get_or_create(phone=phone)
        auth.session_path = session_path
        auth.status = "created"
        auth.save()

        async def send_code():
            app = Client(session_path, api_id=API_ID, api_hash=API_HASH)
            await app.connect()
            result = await app.send_code(phone)
            await app.disconnect()
            return result

        try:
            result = executor.submit(run_in_thread, send_code).result()

            auth.phone_code_hash = result.phone_code_hash
            auth.status = "code_sent"
            auth.save()

            details = {
                "type": str(result.type),
                "next_type": str(result.next_type),
                "timeout": result.timeout,
                "phone_code_hash": result.phone_code_hash,
            }

            print(f"✅ Код отправлен на {phone}")
            print("📦 Ответ Telegram:", details)

            return Response({
                "status": "code_sent",
                "phone": phone,
                "details": details
            })

        except Exception as e:
            auth.status = "error"
            auth.save()
            print(f"❌ Ошибка при отправке кода на {phone}: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CompleteAuthView(APIView):
    """
    POST /api/complete/
    {
      "phone": "+79998887766",
      "code": "12345"
    }
    """

    def post(self, request):
        serializer = CompleteAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        code = serializer.validated_data["code"]

        try:
            auth = TelegramAuth.objects.get(phone=phone)
        except TelegramAuth.DoesNotExist:
            return Response({"error": "Phone not found"}, status=status.HTTP_404_NOT_FOUND)

        async def complete_login():
            app = Client(auth.session_path, api_id=API_ID, api_hash=API_HASH)
            await app.connect()
            await app.sign_in(
                phone_number=phone,
                phone_code_hash=auth.phone_code_hash,
                phone_code=code
            )
            await app.disconnect()
            return True

        try:
            executor.submit(run_in_thread, complete_login).result()
            auth.status = "authorized"
            auth.save()
            print(f"✅ Авторизация завершена для {phone}")
            return Response({"status": "authorized", "session_saved": auth.session_path})
        # except SessionPasswordNeeded:
        #     auth.status = "2fa_required"
        #     auth.save()
        #     return Response({"error": "2FA password required"}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            auth.status = "error"
            auth.save()
            print(f"❌ Ошибка при подтверждении кода для {phone}: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
