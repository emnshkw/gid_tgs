API_ID = 9018428  # 🔹 Твой api_id от https://my.telegram.org
API_HASH = "93732d8d7cd181e163b69ad5079d2020"  # 🔹 Твой api_hash
import asyncio
from django.http import JsonResponse
from rest_framework.views import APIView
from pyrogram import Client
from pyrogram.errors import PhoneCodeExpired, PhoneCodeInvalid
import os
import threading
SESSION_DIR = '/home/fetcher/sessions/'
os.makedirs(SESSION_DIR, exist_ok=True)

# временное хранилище данных между start и complete
TEMP_DATA = {}

# ---- ЕДИНЫЙ event loop в отдельном потоке ----
_loop = None
_thread = None


def ensure_loop():
    """Создаёт или возвращает глобальный event loop в отдельном потоке."""
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
    """Безопасно выполняет асинхронный код в Django."""
    loop = ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


# ---- Django views ----

class StartAuthView(APIView):
    """1️⃣ Отправка кода подтверждения"""
    def post(self, request):
        phone = request.data.get("phone")
        if not phone:
            return JsonResponse({"error": "Phone number required"}, status=400)

        session_path = os.path.join(SESSION_DIR, f"{phone}.session")

        async def send_code():
            async with Client(session_path, api_id=API_ID, api_hash=API_HASH) as app:
                sent_code = await app.send_code(phone)
                return sent_code

        try:
            sent_code = run_async_threadsafe(send_code())
            TEMP_DATA[phone] = {"phone_code_hash": sent_code.phone_code_hash}

            return JsonResponse({
                "status": "code_sent",
                "phone": phone,
                "details": {
                    "type": str(sent_code.type),
                    "phone_code_hash": sent_code.phone_code_hash
                }
            })
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


class CompleteAuthView(APIView):
    """2️⃣ Подтверждение кода"""
    def post(self, request):
        phone = request.data.get("phone")
        code = request.data.get("code")

        if not phone or not code:
            return JsonResponse({"error": "Phone and code required"}, status=400)

        phone_code_hash = TEMP_DATA.get(phone, {}).get("phone_code_hash")
        if not phone_code_hash:
            return JsonResponse({"error": "Missing phone_code_hash"}, status=400)

        session_path = os.path.join(SESSION_DIR, f"{phone}.session")

        async def sign_in():
            async with Client(session_path, api_id=API_ID, api_hash=API_HASH) as app:
                me = await app.sign_in(phone, code, phone_code_hash)
                return me

        try:
            me = run_async_threadsafe(sign_in())
            return JsonResponse({
                "status": "authorized",
                "user": {
                    "id": me.id,
                    "first_name": me.first_name,
                    "phone": me.phone_number
                }
            })
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)