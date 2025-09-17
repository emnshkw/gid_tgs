import os
import builtins
from pyrogram import Client, errors

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

API_FILE = os.path.join(BASE_DIR, "api.txt")

# Читаем API_ID и API_HASH
with open(API_FILE) as f:
    API_ID = int(f.readline().strip())
    API_HASH = f.readline().strip()

def add_session():
    while True:
        phone = input("Введите номер телефона для новой сессии: ")

        # Перехватываем input Pyrogram, чтобы автоматически вставлять номер
        orig_input = builtins.input
        builtins.input = lambda prompt="": phone if "Enter phone number" in prompt else orig_input(prompt)

        session_name = os.path.join(SESSIONS_DIR, phone.replace("+", ""))
        app = Client(session_name, api_id=API_ID, api_hash=API_HASH, workdir=SESSIONS_DIR)
        try:
            app.start()
            print(f"[+] Сессия для {phone} успешно создана!")
        except errors.PhoneCodeInvalid:
            print("[-] Неверный код подтверждения, попробуйте снова.")
        except errors.PhoneNumberInvalid:
            print("[-] Неверный номер телефона, попробуйте снова.")
        except Exception as e:
            print(f"[-] Ошибка создания сессии: {e}")
        else:
            # Проверяем сессию: получаем свой профиль
            try:
                me = app.get_me()
                print(f"[i] Сессия валидна. Вы вошли как {me.first_name} ({me.id})")
            except Exception as e:
                print(f"[-] Ошибка проверки сессии: {e}")
            finally:
                app.stop()

        # Восстанавливаем стандартный input
        builtins.input = orig_input

if __name__ == "__main__":
    add_session()
