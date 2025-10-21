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
# ---- Глобальный event loop ----
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


# ---- Django Views ----

class StartAuthView(APIView):
    """1️⃣ Отправка кода подтверждения"""
    def post(self, request):
        phone = request.data.get("phone")
        if not phone:
            return JsonResponse({"error": "Phone required"}, status=400)

        session_path = os.path.join(SESSION_DIR, f"{phone}.session")

        async def send_code():
            app = Client(session_path, api_id=API_ID, api_hash=API_HASH)
            await app.connect()
            try:
                sent_code = await app.send_code(phone)
                TEMP_DATA[phone] = {
                    "phone_code_hash": sent_code.phone_code_hash
                }
                await app.disconnect()
                return sent_code
            except Exception as e:
                await app.disconnect()
                raise e

        try:
            sent_code = run_async_threadsafe(send_code())
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

        async def complete_login():
            app = Client(session_path, api_id=API_ID, api_hash=API_HASH)
            await app.connect()
            try:
                me = await app.sign_in(
                    phone_number=phone,
                    code=code,
                    phone_code_hash=phone_code_hash
                )
                await app.disconnect()
                return me
            except Exception as e:
                await app.disconnect()
                raise e

        try:
            me = run_async_threadsafe(complete_login())
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