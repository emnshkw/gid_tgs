from rest_framework.parsers import MultiPartParser

API_ID = 9018428  # 🔹 Твой api_id от https://my.telegram.org
API_HASH = "93732d8d7cd181e163b69ad5079d2020"  # 🔹 Твой api_hash
from django.http import JsonResponse
from rest_framework.views import APIView
from .models import TelegramAuth
import os
SESSION_DIR = '/home/fetcher/sessions/'
os.makedirs(SESSION_DIR, exist_ok=True)

class UploadSessionView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        phone = request.data.get("phone")
        file = request.data.get("session_file")

        if not phone or not file:
            return JsonResponse({"error": "phone and session_file are required"}, status=400)

        # Сохраняем файл
        filename = f"{phone}.session"
        path = os.path.join(SESSION_DIR, filename)
        with open(path, "wb") as f:
            for chunk in file.chunks():
                f.write(chunk)

        # Создаём/обновляем запись в модели
        auth_obj, _ = TelegramAuth.objects.get_or_create(
            phone=phone,
            defaults={"session_path": path, "status": "authorized"}
        )
        auth_obj.session_path = path
        auth_obj.status = "authorized"
        auth_obj.save()

        return JsonResponse({
            "status": "success",
            "message": f"Session saved for {phone}",
            "path": path
        })