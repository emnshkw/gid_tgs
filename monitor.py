import asyncio
import aiohttp
import os
import logging
from pyrogram import Client
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# ============ НАСТРОЙКИ ============
DJANGO_BASE = "https://gid-profit.ru/api"
DIALOGS_EP = "/dialogs/"
OUTGOING_EP = "/messages_outgoing/"
MESSAGES_BATCH_EP = "/messages_batch/"
SESSIONS_DIR = "sessions"
API_FILE = os.path.join(BASE_DIR, "api.txt")

LOOP_INTERVAL = 3  # секунды между циклами

# ===================== Чтение API =====================
with open(API_FILE, encoding="utf-8") as f:
    API_ID = int(f.readline().strip())
    API_HASH = f.readline().strip()

LOOP_INTERVAL = 2.0

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ ВСПОМОГАТЕЛЬНЫЕ ============
def django_headers():
    return {"Content-Type": "application/json"}

def load_sessions():
    sessions = {}
    for fname in os.listdir(SESSIONS_DIR):
        if fname.endswith(".session"):
            phone = fname.replace(".session", "")
            path = os.path.join(SESSIONS_DIR, fname)
            sessions[phone] = Client(path, api_id=API_ID, api_hash=API_HASH)
    return sessions

# ============ РАБОЧИЙ КЛАСС ============
class TelegramWorker:
    def __init__(self, session_map, http):
        self.session_map = session_map
        self.http = http
        self.dialog_cache = {}
        self.sem = asyncio.Semaphore(10)
        self.poll_interval = LOOP_INTERVAL

    async def get_or_create_dialog(self, account_phone, chat_id, chat_title, avatar_url=None):
        key = f"{account_phone}:{chat_id}"
        if key in self.dialog_cache:
            return self.dialog_cache[key]
        try:
            async with self.http.get(f"{DJANGO_BASE}{DIALOGS_EP}", headers=django_headers()) as r:
                all_dialogs = await r.json()
            dlg = next((d for d in all_dialogs if d['chat_id'] == chat_id and d['account_phone'] == account_phone), None)

            if not dlg:
                payload = {"account_phone": account_phone, "chat_id": chat_id, "chat_title": chat_title}
                async with self.http.post(f"{DJANGO_BASE}{DIALOGS_EP}", json=payload, headers=django_headers()) as r:
                    dlg = await r.json()

            self.dialog_cache[key] = dlg["id"]
            return dlg["id"]
        except Exception as e:
            logger.error(f"Ошибка get_or_create_dialog: {e}")
            return None

    async def fetch_new_telegram_messages(self, client, account_phone):
        """Чтение новых сообщений"""
        new_messages = []
        async for dialog in client.get_dialogs():
            async for msg in client.get_chat_history(dialog.chat.id, limit=5):
                if not msg or msg.outgoing:
                    continue
                media_list = []
                media_type = None
                file_path = None

                if msg.voice:
                    media_type = "voice"
                    file_path = await msg.download(file_name="downloads/")
                elif msg.video_note:
                    media_type = "video_note"
                    file_path = await msg.download(file_name="downloads/")
                elif msg.video:
                    media_type = "video"
                    file_path = await msg.download(file_name="downloads/")
                elif msg.photo:
                    media_type = "photo"
                    file_path = await msg.download(file_name="downloads/")
                elif msg.document:
                    media_type = "document"
                    file_path = await msg.download(file_name="downloads/")

                if file_path:
                    media_list.append({
                        "media_type": media_type,
                        "file": file_path.replace("\\", "/"),
                    })

                dialog_id = await self.get_or_create_dialog(account_phone, dialog.chat.id, dialog.chat.title or "NoTitle")

                new_messages.append({
                    "telegram_id": msg.id,
                    "sender_name": msg.from_user.first_name if msg.from_user else "Unknown",
                    "text": msg.text or "",
                    "media": media_list,
                    "dialog": dialog_id,
                })
        return new_messages

    async def handle_outgoing_message(self, client, account_phone, msg):
        """Отправка сообщений из Django в Telegram"""
        try:
            async with self.http.get(f"{DJANGO_BASE}{DIALOGS_EP}", headers=django_headers()) as r:
                all_dialogs = await r.json()
            dlg = next((d for d in all_dialogs if d['id'] == msg['dialog']), None)
            if not dlg:
                logger.warning(f"[{account_phone}] Диалог {msg['dialog']} не найден")
                return

            peer = await client.get_chat(int(dlg['chat_id']))
            text = msg.get("text", "")
            media = msg.get("media", [])

            if media:
                m = media[0]
                file = m.get("file")
                await client.send_document(peer.id, file)
            elif text:
                await client.send_message(peer.id, text)

            # После успешной отправки — удаляем сообщение
            async with self.http.delete(f"{DJANGO_BASE}{OUTGOING_EP}{msg['id']}/", headers=django_headers()):
                pass

        except Exception as e:
            logger.error(f"[{account_phone}] Ошибка отправки: {e}")

    async def poll_incoming_once(self, client, account_phone):
        try:
            new_messages = await self.fetch_new_telegram_messages(client, account_phone)
            if not new_messages:
                await asyncio.sleep(self.poll_interval)
                return

            payload = {"messages": new_messages}
            async with self.http.post(f"{DJANGO_BASE}{MESSAGES_BATCH_EP}", json=payload, headers=django_headers()) as r:
                if r.status != 201:
                    logger.warning(f"Ошибка пакетной отправки: {r.status}, {await r.text()}")

        except Exception as e:
            logger.error(f"poll_incoming_once error: {e}")
            await asyncio.sleep(self.poll_interval)

    async def poll_outgoing_once(self, client, account_phone):
        try:
            async with self.http.get(f"{DJANGO_BASE}{OUTGOING_EP}", headers=django_headers()) as r:
                msgs = await r.json()

            if not msgs:
                await asyncio.sleep(self.poll_interval)
                return

            await asyncio.gather(*(self.handle_outgoing_message(client, account_phone, m) for m in msgs))
        except Exception as e:
            logger.error(f"poll_outgoing_once error: {e}")
            await asyncio.sleep(self.poll_interval)

    async def run_for_client(self, client, account_phone):
        await client.start()
        logger.info(f"[{account_phone}] client started")
        while True:
            await asyncio.gather(
                self.poll_incoming_once(client, account_phone),
                self.poll_outgoing_once(client, account_phone)
            )

    async def run_loop(self):
        tasks = []
        for phone, client in self.session_map.items():
            tasks.append(self.run_for_client(client, phone))
        await asyncio.gather(*tasks)

# ============ ЗАПУСК ============
async def main():
    session_map = load_sessions()
    conn = aiohttp.TCPConnector(limit=100)
    async with aiohttp.ClientSession(connector=conn) as http:
        worker = TelegramWorker(session_map, http)
        await worker.run_loop()

if __name__ == "__main__":
    asyncio.run(main())
