import os
import requests
from pyrogram import Client, errors

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

API_FILE = os.path.join(BASE_DIR, "api.txt")
SERVER_UPLOAD_URL = "https://gid-profit.ru/pyrogram_api/send/"  # замените на ваш URL

# Читаем API_ID и API_HASH
with open(API_FILE) as f:
    API_ID = int(f.readline().strip())
    API_HASH = f.readline().strip()
print("Ожидайте, программа загружается...")
def add_session():
    while True:
        phone = input("Введите номер телефона для новой сессии (с +7): ").replace(' ','').replace('+','')
        session_name = os.path.join(SESSIONS_DIR, phone)

        app = Client(session_name, api_id=API_ID, api_hash=API_HASH, workdir=SESSIONS_DIR)
        try:
            # Подключаемся
            app.connect()

            # 1️⃣ Отправляем код на Telegram APP (APP push)
            sent_code = app.send_code(phone)

            # 2️⃣ Вводим код вручную через кастомный prompt
            code = input("Введите код из Telegram: ").strip()

            # 3️⃣ Завершаем авторизацию
            me = app.sign_in(
                phone_number=phone,
                phone_code_hash=sent_code.phone_code_hash,
                phone_code=code
            )

            print(f"[i] Сессия валидна. Вы вошли как {me.first_name} ({me.id})")

            # 4️⃣ Отправка файла сессии на сервер
            session_file_path = os.path.join(SESSIONS_DIR, f"{phone}.session")
            with open(session_file_path, "rb") as f:
                files = {"session_file": (f"{phone}.session", f)}
                data = {"phone": phone}
                resp = requests.post(SERVER_UPLOAD_URL, data=data, files=files)
                if resp.json()['status'] == 'success':
                    print(f"[i] Ответ сервера: аккаунт успешно добавлен!")

        except errors.PhoneCodeInvalid:
            print("[-] Неверный код подтверждения, попробуйте снова.")
        except errors.PhoneNumberInvalid:
            print("[-] Неверный номер телефона, попробуйте снова.")
        except Exception as e:
            print(f"[-] Ошибка создания сессии: {e}")


if __name__ == "__main__":
    add_session()
