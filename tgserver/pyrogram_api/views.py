API_ID = 9018428  # 🔹 Твой api_id от https://my.telegram.org
API_HASH = "93732d8d7cd181e163b69ad5079d2020"  # 🔹 Твой api_hash
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status


executor = ThreadPoolExecutor(max_workers=4)
active_sessions = {}


def run_in_thread(coro_func, *args, **kwargs):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro_func(*args, **kwargs))


class StartAuthView(APIView):
    def post(self, request):
        phone = request.data.get("phone")
        session_path = request.data.get("session_path")
        if not phone or not session_path:
            return Response({"error": "phone and session_path required"}, status=400)

        async def send_code():
            app = Client(
                session_path,
                api_id=API_ID,
                api_hash=API_HASH,
                phone_number=phone
            )
            await app.connect()
            sent = await app.send_code(phone)
            # сохраняем сам клиент в память!
            active_sessions[phone] = {
                "client": app,
                "phone_code_hash": sent.phone_code_hash,
                "session_path": session_path
            }
            return sent.phone_code_hash

        try:
            phone_code_hash = executor.submit(run_in_thread, send_code).result()
            return Response({"status": "code_sent"})
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class CompleteAuthView(APIView):
    def post(self, request):
        phone = request.data.get("phone")
        code = request.data.get("code")
        if not phone or not code:
            return Response({"error": "phone and code required"}, status=400)

        if phone not in active_sessions:
            return Response({"error": "no active session"}, status=400)

        phone_code_hash = active_sessions[phone]["phone_code_hash"]
        app = active_sessions[phone]["client"]

        async def complete_login():
            await app.sign_in(
                phone_number=phone,
                phone_code_hash=phone_code_hash,
                phone_code=code
            )
            await app.disconnect()
            return True

        try:
            executor.submit(run_in_thread, complete_login).result()
            del active_sessions[phone]
            return Response({"status": "authorized"})
        except SessionPasswordNeeded:
            return Response({"error": "2FA password required"}, status=401)
        except Exception as e:
            return Response({"error": str(e)}, status=400)
