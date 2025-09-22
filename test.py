import os
from pyrogram import Client, errors

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
MEDIA_DIR = os.path.join(BASE_DIR, "tgserver", "media")
os.makedirs(MEDIA_DIR, exist_ok=True)
API_FILE = os.path.join(BASE_DIR, "api.txt")
ACCOUNTS_FILE = os.path.join(BASE_DIR, "accounts.txt")
API_BASE = "http://127.0.0.1/api"

# --- Чтение API ID / HASH ---
with open(API_FILE, encoding="utf-8") as f:
    API_ID = int(f.readline().strip())
    API_HASH = f.readline().strip()

# --- Номера аккаунтов (в accounts.txt номера начинаются с '+') ---
ACCOUNTS = []
for session_file in os.listdir('sessions'):
    ACCOUNTS.append(session_file.split('.')[0])

SESSIONS_DIR = "sessions"


def test_session(session_path: str):
    session_name = os.path.splitext(os.path.basename(session_path))[0]
    print(session_name)
    app = Client(
        name=session_name,
        api_id=API_ID,
        api_hash=API_HASH,
        workdir=SESSIONS_DIR,
        in_memory=False
    )

    try:
        app.load_session()  # <-- Загружаем, но не авторизуемся
    except Exception:
        return session_name, False, "❌ Битый или пустой .session"

    try:
        app.start()
        me = app.get_me()
        app.stop()
        return session_name, True, f"✅ {me.first_name} (id {me.id})"
    except errors.PhoneCodeInvalid:
        print("[-] Неверный код подтверждения, попробуйте снова.")
    except errors.PhoneNumberInvalid:
        print("[-] Неверный номер телефона, попробуйте снова.")
    except Exception as e:
        print(f"[-] Ошибка создания сессии: {e}")



def test_all_sessions():
    results = []
    for file in os.listdir(SESSIONS_DIR):
        if file.endswith(".session"):
            results.append(test_session(os.path.join(SESSIONS_DIR, file)))
    return results


if __name__ == "__main__":
    for session, ok, msg in test_all_sessions():
        print(f"[{session}] {msg}")
