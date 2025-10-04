import asyncio
import os
import glob
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
from pyrogram import Client
from pyrogram.types import Message, InputMediaPhoto, InputMediaVideo, InputMediaDocument
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ======== Конфигурация ========
API_FILE = os.path.join(BASE_DIR, "api.txt")
ACCOUNTS_FILE = os.path.join(BASE_DIR, "accounts.txt")
API_BASE = "http://127.0.0.1:8001/api"

# --- Чтение API ID / HASH ---
with open(API_FILE, encoding="utf-8") as f:
    API_ID = int(f.readline().strip())
    API_HASH = f.readline().strip()

SESSIONS_DIR = os.getenv("SESSIONS_DIR", "sessions")
DJANGO_BASE = os.getenv("DJANGO_BASE", "http://127.0.0.1:8001/api")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))

# ======== Эндпоинты ========
PROFILES_EP = "/profiles/"
DIALOGS_EP = "/dialogs/"
MESSAGES_EP = "/messages/"
MESSAGES_MEDIA_EP = "/messages_media/"

# ======== Вспомогательные функции ========
def session_phone_from_path(p: Path):
    """Телефон из имени файла .session"""
    name = p.name
    if name.endswith(".session"):
        name = name[:-8]
    return "+" + name if not name.startswith("+") else name

def django_headers():
    return {"Content-Type": "application/json"}

# ======== Основной класс Worker ========
class TelegramWorker:
    def __init__(self):
        self.clients = {}  # phone -> Client
        self.session_map = {}  # phone -> Client
        self.http = None

    async def start(self):
        self.http = aiohttp.ClientSession()
        await self._load_sessions()
        asyncio.create_task(self.poll_outgoing_loop())

    async def stop(self):
        for client in self.clients.values():
            await client.stop()
        if self.http:
            await self.http.close()

    async def _load_sessions(self):
        p = Path(SESSIONS_DIR)
        for fpath in glob.glob(str(p / "*.session")):
            phone = session_phone_from_path(Path(fpath))
            await self._start_client(fpath, phone)

    async def _start_client(self, session_path, phone):
        from pathlib import Path

        session_file = Path(session_path)
        session_name = session_file.stem  # убираем .session
        print(session_name)
        client = Client(
            name=session_name,
            api_id=API_ID,
            api_hash=API_HASH,
            workdir=str(session_file.parent)
        )
        await client.start()
        print(f"[{phone}] client started, me={await client.get_me()}")
        self.clients[phone] = client
        self.session_map[phone] = client
        # Вешаем handler входящих сообщений
        client.add_handler(lambda c, m: asyncio.create_task(self.handle_incoming_message(phone, m)))
        print(f"[{phone}] client started")

    async def handle_incoming_message(self, phone, message: Message):
        print(f"[{phone}] Incoming message from {message.chat.id}: {message.text}")
        """Сохраняем входящее сообщение в Django"""
        dialog_id = await self.get_or_create_dialog(phone, message.chat)
        if not dialog_id:
            return

        sender = getattr(message.from_user, "first_name", "Unknown")
        text = message.text or message.caption or ""
        date_iso = message.date.astimezone(timezone.utc).isoformat()

        # Получаем медиа
        media_files = await self.extract_media(message)

        payload = {
            "dialog": dialog_id,
            "sender_name": sender,
            "text": text,
            "date": date_iso,
            "delivered": True,
            "telegram_id": message.message_id
        }

        if media_files:
            files_to_send = []
            for m in media_files:
                f = open(m['file_path'], "rb")
                files_to_send.append(("files", (os.path.basename(m['file_path']), f)))
            try:
                async with self.http.post(DJANGO_BASE+MESSAGES_MEDIA_EP, data=payload, headers=django_headers(), files=files_to_send) as resp:
                    if resp.status in (200,201):
                        print(f"[{phone}] Incoming media message saved")
            finally:
                for _, (_, f) in files_to_send:
                    f.close()
        else:
            async with self.http.post(DJANGO_BASE+MESSAGES_EP, json=payload, headers=django_headers()) as resp:
                if resp.status in (200,201):
                    print(f"[{phone}] Incoming message saved")

    async def get_or_create_dialog(self, phone, chat):
        """Находим или создаем диалог в Django"""
        try:
            async with self.http.get(DJANGO_BASE+DIALOGS_EP, headers=django_headers()) as r:
                dialogs = await r.json()
                for dlg in dialogs:
                    if dlg['account_phone'] == phone and str(dlg['chat_id']) == str(chat.id):
                        return dlg['id']
            # Создание нового диалога
            payload = {"account_phone": phone, "chat_id": str(chat.id), "chat_title": chat.title or str(chat.id)}
            files = None
            if getattr(chat, "photo", None):
                tmpfile = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                await Client.download_media(Client, chat.photo.big_file_id, file_name=tmpfile.name)
                files = {"avatar": open(tmpfile.name,"rb")}
            async with self.http.post(DJANGO_BASE+DIALOGS_EP, data=payload, headers=django_headers(), files=files) as r:
                if r.status in (200,201):
                    res = await r.json()
                    return res.get("id")
        except Exception as e:
            print("get_or_create_dialog error:", e)
        return None

    async def extract_media(self, message):
        """Извлекаем медиа файлы из сообщения"""
        media_list = []
        suffix = None
        if message.photo:
            suffix = ".jpg"
        elif message.video:
            suffix = ".mp4"
        elif message.document:
            suffix = os.path.splitext(message.document.file_name)[1] or ".dat"
        else:
            return media_list

        tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        await Client.download_media(Client, message, file_name=tmpfile.name)
        media_list.append({"file_path": tmpfile.name, "media_type": "photo" if suffix==".jpg" else "document"})
        return media_list

    async def poll_outgoing_loop(self):
        while True:
            try:
                await self.poll_outgoing_once()
            except Exception as e:
                print("poll_outgoing_loop error:", e)
            await asyncio.sleep(POLL_INTERVAL)

    async def poll_outgoing_once(self):
        try:
            async with self.http.get(DJANGO_BASE+MESSAGES_EP+"?delivered=false", headers=django_headers()) as r:
                messages = await r.json()
            for msg in messages:
                dialog_id = msg['dialog']  # это int
                # Получаем сам диалог
                async with self.http.get(f"{DJANGO_BASE}{DIALOGS_EP}{dialog_id}/", headers=django_headers()) as r:
                    dlg = await r.json()
                phone = dlg['account_phone']
                chat_id = dlg['chat_id']
                phone = msg['dialog']['account_phone']
                chat_id = msg['dialog']['chat_id']
                text = msg['text']
                media = msg.get("media")
                client = self.session_map.get(phone)
                if not client:
                    continue

                if media:
                    for m in media:
                        ext = os.path.splitext(m['file_path'])[1]
                        if ext in [".jpg",".png"]:
                            await client.send_photo(chat_id, m['file_path'], caption=text)
                        else:
                            await client.send_document(chat_id, m['file_path'], caption=text)
                else:
                    await client.send_message(chat_id, text)

                # Отметка доставленного
                await self.http.delete(f"{DJANGO_BASE}{MESSAGES_EP}{msg['id']}/", json={"delivered": True}, headers=django_headers())
                print(f"[{phone}] Sent message {msg['id']}")
        except Exception as e:
            print("poll_outgoing_once error:", e)


# ======== Запуск ========
async def main():
    worker = TelegramWorker()
    await worker.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("Stopping worker...")
    finally:
        await worker.stop()

if __name__ == "__main__":
    asyncio.run(main())
