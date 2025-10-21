API_ID = 9018428  # 🔹 Твой api_id от https://my.telegram.org
API_HASH = "93732d8d7cd181e163b69ad5079d2020"  # 🔹 Твой api_hash
import asyncio
from django.http import JsonResponse
from rest_framework.views import APIView
from pyrogram import Client
from pyrogram.errors import PhoneCodeExpired, PhoneCodeInvalid
import os

SESSIONS_DIR = '/home/fetcher/sessions/'
os.makedirs(SESSIONS_DIR, exist_ok=True)

# временное хранилище данных между start и complete
TEMP_DATA = {}


class StartAuthView(APIView):
    def post(self, request):
        phone = request.data.get("phone")
        if not phone:
            return JsonResponse({"error": "phone required"}, status=400)

        session_path = os.path.join(SESSIONS_DIR, f"{phone}.session")

        async def send_code():
            async with Client(
                session_path,
                api_id=API_ID,
                api_hash=API_HASH,
                in_memory=False,
                phone_number=phone,
            ) as app:
                result = await app.send_code(phone)
                TEMP_DATA[phone] = {
                    "phone_code_hash": result.phone_code_hash,
                    "session_path": session_path,
                }
                return result

        result = asyncio.run(send_code())

        return JsonResponse({
            "status": "code_sent",
            "phone": phone,
            "details": {
                "type": str(result.type),
                "next_type": str(result.next_type),
                "timeout": result.timeout,
                "phone_code_hash": result.phone_code_hash,
            },
        })


class CompleteAuthView(APIView):
    def post(self, request):
        phone = request.data.get("phone")
        code = request.data.get("code")

        if not phone or not code:
            return JsonResponse({"error": "phone and code required"}, status=400)

        temp = TEMP_DATA.get(phone)
        if not temp:
            return JsonResponse({"error": "no pending session for this phone"}, status=400)

        phone_code_hash = temp["phone_code_hash"]
        session_path = temp["session_path"]

        async def complete_login():
            async with Client(
                session_path,
                api_id=API_ID,
                api_hash=API_HASH,
                in_memory=False,
                phone_number=phone,
            ) as app:
                try:
                    await app.sign_in(phone, phone_code_hash, code)
                    me = await app.get_me()
                    return {"status": "success", "user": me.first_name}
                except PhoneCodeInvalid:
                    return {"error": "invalid_code"}
                except PhoneCodeExpired:
                    return {"error": "code_expired"}
                except Exception as e:
                    return {"error": str(e)}

        result = asyncio.run(complete_login())
        return JsonResponse(result)