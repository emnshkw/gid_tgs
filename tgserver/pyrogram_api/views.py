API_ID = 9018428  # 🔹 Твой api_id от https://my.telegram.org
API_HASH = "93732d8d7cd181e163b69ad5079d2020"  # 🔹 Твой api_hash
import asyncio
from django.http import JsonResponse
from rest_framework.views import APIView
from pyrogram import Client
from pyrogram.errors import PhoneCodeExpired, PhoneCodeInvalid
import os

SESSION_DIR = '/home/fetcher/sessions/'
os.makedirs(SESSION_DIR, exist_ok=True)

# временное хранилище данных между start и complete
TEMP_DATA = {}

# создаём единый event loop для всего Django-процесса
LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)


def run_async(coro):
    """Безопасно запускает асинхронный код в синхронной Django-вьюхе."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


class StartAuthView(APIView):
    def post(self, request):
        phone = request.data.get("phone")
        if not phone:
            return JsonResponse({"error": "Phone number required"}, status=400)

        session_path = os.path.join(SESSION_DIR, f"{phone}.session")

        async def send_code():
            async with Client(session_path, api_id=API_ID, api_hash=API_HASH) as app:
                sent_code = await app.send_code(phone)
                TEMP_DATA[phone] = {
                    "phone_code_hash": sent_code.phone_code_hash,
                }
                return sent_code

        try:
            sent_code = run_async(send_code())
            return JsonResponse({
                "status": "code_sent",
                "phone": phone,
                "details": {
                    "type": str(sent_code.type),
                    "phone_code_hash": sent_code.phone_code_hash,
                }
            })
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


class CompleteAuthView(APIView):
    def post(self, request):
        phone = request.data.get("phone")
        code = request.data.get("code")

        if not phone or not code:
            return JsonResponse({"error": "Phone and code required"}, status=400)

        session_path = os.path.join(SESSION_DIR, f"{phone}.session")
        phone_code_hash = TEMP_DATA.get(phone, {}).get("phone_code_hash")

        async def complete_login():
            async with Client(session_path, api_id=API_ID, api_hash=API_HASH) as app:
                await app.sign_in(phone_number=phone, code=code, phone_code_hash=phone_code_hash)
                me = await app.get_me()
                return me

        try:
            me = run_async(complete_login())
            return JsonResponse({
                "status": "authorized",
                "user": {"id": me.id, "first_name": me.first_name, "phone": me.phone_number},
            })
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)