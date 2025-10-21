API_ID = 9018428  # 🔹 Твой api_id от https://my.telegram.org
API_HASH = "93732d8d7cd181e163b69ad5079d2020"  # 🔹 Твой api_hash
import asyncio
from django.http import JsonResponse
from rest_framework.views import APIView
from pyrogram import Client
from .models import TelegramAuth
from pyrogram.errors import PhoneCodeExpired, PhoneCodeInvalid
import os
import threading
import time
SESSION_DIR = '/home/fetcher/sessions/'
os.makedirs(SESSION_DIR, exist_ok=True)

# ---- asyncio loop в отдельном потоке ----
_loop = None
_thread = None

def ensure_loop():
    global _loop, _thread
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        def run_loop():
            asyncio.set_event_loop(_loop)
            _loop.run_forever()
        _thread = threading.Thread(target=run_loop, daemon=True)
        _thread.start()
    return _loop

def run_async_threadsafe(coro):
    loop = ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


# ---- Вьюхи ----

class StartAuthView(APIView):
    """Отправка APP-кода"""
    def post(self, request):
        phone = request.data.get("phone")
        if not phone:
            return JsonResponse({"error": "Phone required"}, status=400)

        session_path = os.path.join(SESSION_DIR, f"{phone}.session")
        auth_obj, _ = TelegramAuth.objects.get_or_create(
            phone=phone,
            defaults={"session_path": session_path, "status": "created"}
        )

        async def send_code():
            app = Client(session_path, api_id=API_ID, api_hash=API_HASH)
            await app.connect()
            try:
                sent_code = await app.send_code(phone)  # Telegram решает APP или SMS
                await app.disconnect()
                return sent_code
            except Exception as e:
                await app.disconnect()
                raise e

        try:
            sent_code = run_async_threadsafe(send_code())
            auth_obj.phone_code_hash = sent_code.phone_code_hash
            auth_obj.status = "code_sent"
            auth_obj.save()

            return JsonResponse({
                "status": "code_sent",
                "phone": phone,
                "message": (
                    "APP-код отправлен на последнее активное устройство. "
                    "Введите его в /complete/ через Postman"
                )
            })
        except Exception as e:
            auth_obj.status = "error"
            auth_obj.save()
            return JsonResponse({"error": str(e)}, status=500)


class CompleteAuthView(APIView):
    """Завершение авторизации через код с устройства"""
    def post(self, request):
        phone = request.data.get("phone")
        code = request.data.get("code")

        if not all([phone, code]):
            return JsonResponse({"error": "phone and code required"}, status=400)

        try:
            auth_obj = TelegramAuth.objects.get(phone=phone)
        except TelegramAuth.DoesNotExist:
            return JsonResponse({"error": "Phone not found"}, status=400)

        if not auth_obj.phone_code_hash:
            return JsonResponse({"error": "No code sent, request /start first"}, status=400)

        # TTL кода 2 минуты
        if time.time() - auth_obj.updated_at.timestamp() > 120:
            auth_obj.status = "error"
            auth_obj.save()
            return JsonResponse({"error": "Code expired, request new code"}, status=400)

        async def complete_login():
            app = Client(auth_obj.session_path, api_id=API_ID, api_hash=API_HASH)
            await app.connect()
            try:
                me = await app.sign_in(
                    phone_number=phone,
                    phone_code_hash=auth_obj.phone_code_hash,
                    phone_code=code
                )
                await app.disconnect()
                return me
            except Exception as e:
                await app.disconnect()
                raise e

        try:
            me = run_async_threadsafe(complete_login())
            auth_obj.status = "authorized"
            auth_obj.save()
            return JsonResponse({
                "status": "authorized",
                "user": {
                    "id": me.id,
                    "first_name": me.first_name,
                    "phone": me.phone_number
                }
            })
        except Exception as e:
            auth_obj.status = "error"
            auth_obj.save()
            return JsonResponse({"error": str(e)}, status=500)