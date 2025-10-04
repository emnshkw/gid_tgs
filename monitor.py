import os
import asyncio
import aiohttp
import tempfile
from pyrogram import Client
from pyrogram.types import InputMediaPhoto, InputMediaVideo, InputMediaDocument

# ===================== Настройки =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
API_FILE = os.path.join(BASE_DIR, "api.txt")

DJANGO_BASE = "https://gid-profit.ru"
DIALOGS_EP = "/api/dialogs/"
MESSAGES_EP = "/api/messages/"

LOOP_INTERVAL = 3  # секунды между циклами

# ===================== Чтение API =====================
with open(API_FILE, encoding="utf-8") as f:
    API_ID = int(f.readline().strip())
    API_HASH = f.readline().strip()

# ===================== Заголовки для Django =====================
def django_headers():
    return {"Accept": "application/json"}
def get_input_media(file_path, caption=None):
    ext = file_path.lower().split(".")[-1]
    if ext in ["jpg", "jpeg", "png", "gif", "webp"]:
        return InputMediaPhoto(file_path, caption=caption)
    elif ext in ["mp4", "mov", "avi", "mkv"]:
        return InputMediaVideo(file_path, caption=caption)
    else:
        return InputMediaDocument(file_path, caption=caption)

# --- Скачиваем файл с Django ---
async def download_django_file(http: aiohttp.ClientSession, file_url: str):
    async with http.get(file_url) as resp:
        if resp.status != 200:
            print(f"Не удалось скачать файл {file_url}")
            return None
        suffix = os.path.splitext(file_url)[-1] or ".dat"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        content = await resp.read()
        tmp.write(content)
        tmp.close()
        return tmp.name

# --- Отправка сообщения с медиа из Django ---
async def send_django_message(client, http, msg, chat_id):
    """
    msg: словарь сообщения из Django API
    chat_id: ID Telegram чата
    client: pyrogram.Client
    http: aiohttp.ClientSession
    """
    text = msg.get("text", "")
    media_list = msg.get("media", [])

    if media_list:
        tmp_files = []
        try:
            for i, m in enumerate(media_list):
                url = f"{DJANGO_BASE}{m['file']}"
                local_path = await download_django_file(http, url)
                if not local_path:
                    continue
                tmp_files.append(local_path)
                caption = text if i == 0 else None
                media_obj = get_input_media(local_path, caption=caption)

                # Отправляем нужный тип медиа
                if isinstance(media_obj, InputMediaPhoto):
                    await client.send_photo(chat_id, local_path, caption=caption)
                elif isinstance(media_obj, InputMediaVideo):
                    await client.send_video(chat_id, local_path, caption=caption)
                else:
                    await client.send_document(chat_id, local_path, caption=caption)

        finally:
            # Удаляем временные файлы
            for f in tmp_files:
                try:
                    os.remove(f)
                except Exception:
                    pass

    else:
        # Если только текст
        await client.send_message(chat_id, text)

# ===================== Загрузка сессий =====================
def load_sessions():
    sessions = {}
    for session_file in os.listdir(SESSIONS_DIR):
        if session_file.endswith(".session"):
            phone = os.path.splitext(session_file)[0]
            client = Client(
                os.path.join(SESSIONS_DIR, phone),
                api_id=API_ID,
                api_hash=API_HASH,
                workdir=SESSIONS_DIR
            )
            sessions[phone] = client
    return sessions

# ===================== Функции =====================
async def send_safe(client: Client, chat_id, text=None, media_files=None):
    try:
        chat = await client.get_chat(chat_id)
    except Exception as e:
        print(f"Ошибка get_chat({chat_id}): {e}")
        return False

    # Отправка медиа
    if media_files:
        for i, m in enumerate(media_files):
            path = m["file"]
            media_type = m.get("media_type")
            caption = text if i == 0 else None
            try:
                if media_type == "photo":
                    await client.send_photo(chat.id, path, caption=caption)
                elif media_type == "video":
                    await client.send_video(chat.id, path, caption=caption)
                else:
                    await client.send_document(chat.id, path, caption=caption)
            except Exception as e:
                print(f"Ошибка отправки медиа {path}: {e}")
        text = None  # caption только для первого медиа

    # Отправка текста
    if text:
        try:
            await client.send_message(chat.id, text)
        except Exception as e:
            print(f"Ошибка отправки текста: {e}")
            return False

    return True

async def message_exists_in_django(http, dialog_id, telegram_id):
    """Проверка существования сообщения в Django по dialog_id + telegram_id"""
    url = f"{DJANGO_BASE}{MESSAGES_EP}?dialog={dialog_id}&telegram_id={telegram_id}"
    async with http.get(url, headers=django_headers()) as r:
        data = await r.json()
    return bool(data)
import os
import aiohttp
import tempfile

async def post_message_to_django(http: aiohttp.ClientSession, payload: dict, media_list: list):
    """
    Отправка сообщения в Django с поддержкой медиа через aiohttp.

    payload: dict с полями сообщения (dialog, sender_name, text, date, telegram_id и т.д.)
    media_list: список словарей {"file": ..., "media_type": ...}
    """
    form = aiohttp.FormData()

    # --- Добавляем обычные поля ---
    for key, value in payload.items():
        form.add_field(key, str(value))

    # --- Добавляем файлы ---
    file_objects = []
    try:
        for m in media_list:
            path = m["file"]
            if not os.path.exists(path):
                continue
            f = open(path, "rb")
            file_objects.append(f)
            filename = os.path.basename(path)
            media_type = m.get("media_type", "application/octet-stream")
            form.add_field(
                "files",
                f,
                filename=filename,
                content_type=media_type
            )

        async with http.post(f"{DJANGO_BASE}/api/messages_media/", data=form) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                print(f"Ошибка создания сообщения: {resp.status} {text}")
                return False
            return await resp.json()
    finally:
        # Закрываем все открытые файлы
        for f in file_objects:
            f.close()

# ===================== Worker =====================
class TelegramWorker:
    def __init__(self, session_map, http):
        self.session_map = session_map
        self.http = http
        self.dialogs_map = {}  # phone -> {chat_id: chat_object}

    # --------------------- Инициализация ---------------------
    async def init_dialogs(self):
        for phone, client in self.session_map.items():
            try:
                await client.start()
                self.dialogs_map[phone] = {}
                async for dialog in client.get_dialogs(limit=0):
                    self.dialogs_map[phone][dialog.chat.id] = dialog.chat
                print(f"[{phone}] Loaded {len(self.dialogs_map[phone])} dialogs")
            except Exception as e:
                print(f"[{phone}] Failed to load dialogs: {e}")

    # --------------------- Django → Telegram ---------------------
    async def poll_outgoing_once(self):
        """
        Берем все сообщения с delivered=false, отправляем их в Telegram,
        и после успешной отправки удаляем из Django.
        """
        try:
            # 1. Берём все недоставленные сообщения
            async with self.http.get(f"{DJANGO_BASE}{MESSAGES_EP}?delivered=false", headers=django_headers()) as r:
                messages = await r.json()

            for msg in messages:
                dialog_id = msg['dialog']

                # 2. Получаем диалог из Django
                async with self.http.get(f"{DJANGO_BASE}{DIALOGS_EP}", headers=django_headers()) as r:
                    all_dialogs = await r.json()
                dlg = next((d for d in all_dialogs if d['id'] == dialog_id), None)
                if not dlg:
                    continue

                phone = dlg['account_phone']
                chat_id = dlg['chat_id']
                client = self.session_map.get(phone)
                if not client:
                    continue

                # 3. Отправляем сообщение
                try:
                    await send_django_message(client, self.http, msg, chat_id)

                    # 4. После успешной отправки — удаляем сообщение из Django
                    await self.http.delete(f"{DJANGO_BASE}{MESSAGES_EP}{msg['id']}/", headers=django_headers())
                    print(f"[{phone}] Message {msg['id']} sent and removed from Django.")

                except Exception as e:
                    print(f"[{phone}] Error sending message {msg['id']}: {e}")

        except Exception as e:
            print("poll_outgoing_once error:", e)

    # --------------------- Telegram → Django ---------------------
    async def fetch_messages_for_account(self, client, phone):
        async for dialog in client.get_dialogs(limit=0):
            chat = dialog.chat
            chat_id = chat.id
            chat_title = chat.title or chat.first_name or str(chat_id)

            # Получаем dialog_id в Django
            async with self.http.get(DJANGO_BASE + DIALOGS_EP, headers=django_headers()) as r:
                all_dialogs = await r.json()
            dlg = next((d for d in all_dialogs if d['chat_id'] == chat_id and d['account_phone'] == phone), None)
            if not dlg:
                payload = {"account_phone": phone, "chat_id": chat_id, "chat_title": chat_title}
                async with self.http.post(DJANGO_BASE + DIALOGS_EP, data=payload) as r:
                    dlg = await r.json()
            dialog_id = dlg['id']

            # История сообщений
            async for msg in client.get_chat_history(chat_id, limit=100):
                tg_id = msg.id
                exists = await message_exists_in_django(self.http, dialog_id, tg_id)
                if exists:
                    continue

                text = getattr(msg, "text", "") or ""
                date_iso = msg.date.isoformat()

                # Медиа
                media_list = []
                if msg.photo or msg.video or msg.document:
                    suffix = ".jpg" if msg.photo else ".mp4" if msg.video else os.path.splitext(msg.document.file_name)[-1]
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
                        path = await client.download_media(msg, file_name=tf.name)
                        media_type = "photo" if msg.photo else "video" if msg.video else "document"
                        media_list.append({"file": path, "media_type": media_type})

                # Создаём сообщение
                payload = {
                    "dialog": dialog_id,
                    "sender_name": getattr(msg.from_user, "first_name", "Unknown") if msg.from_user else "Unknown",
                    "text": text,
                    "date": date_iso,
                    "telegram_id": tg_id,
                    "delivered": True
                }

                files_to_send = []
                for m in media_list:
                    f = open(m["file"], "rb")
                    files_to_send.append(("files", (os.path.basename(m["file"]), f)))

                try:
                    await post_message_to_django(self.http, payload, media_list)
                finally:
                    for _, (_, f) in files_to_send:
                        f.close()

    # --------------------- Главный цикл ---------------------
    async def run_loop(self):
        await self.init_dialogs()
        print("All dialogs loaded, starting main loop...")

        try:
            while True:
                # 1. Django → Telegram
                await self.poll_outgoing_once()

                # 2. Telegram → Django
                for phone, client in self.session_map.items():
                    await self.fetch_messages_for_account(client, phone)

                await asyncio.sleep(LOOP_INTERVAL)

        except KeyboardInterrupt:
            print("Stopping worker...")
        finally:
            for client in self.session_map.values():
                try:
                    await client.stop()
                except Exception:
                    pass

# ===================== Main =====================
async def main():
    session_map = load_sessions()
    async with aiohttp.ClientSession() as http:
        worker = TelegramWorker(session_map, http)
        await worker.run_loop()

if __name__ == "__main__":
    asyncio.run(main())
