import os
import asyncio
import aiohttp
from datetime import datetime
from pyrogram import Client, errors
from pyrogram.types import InputMediaPhoto, InputMediaVideo, InputMediaDocument

# === НАСТРОЙКИ ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
API_FILE = os.path.join(BASE_DIR, "api.txt")
DJANGO_BASE = "https://gid-profit.ru/api"
LOOP_INTERVAL = 4  # секунд между циклами опроса

# === ЧТЕНИЕ API ID/HASH ===
with open(API_FILE, encoding="utf-8") as f:
    API_ID = int(f.readline().strip())
    API_HASH = f.readline().strip()

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def django_headers():
    return {"Accept": "application/json"}

def load_sessions():
    """Загружает все сессии из папки sessions"""
    sessions = {}
    for fname in os.listdir(SESSIONS_DIR):
        if fname.endswith(".session"):
            phone = fname.replace(".session", "")
            session_name = os.path.join(SESSIONS_DIR, phone)
            session_name = os.path.splitext(session_name)[0]  # без .session
            sessions[phone] = Client(session_name, api_id=API_ID, api_hash=API_HASH)
    return sessions

# === ОСНОВНОЙ КЛАСС ===
class TelegramWorker:
    def __init__(self, session_map, http):
        self.session_map = session_map
        self.http = http

    async def run_loop(self):
        """Основной цикл"""
        clients = []

        # Запуск всех клиентов
        for phone, client in self.session_map.items():
            try:
                await client.start()
                me = await client.get_me()
                print(f"[{phone}] ✅ client started: {me.first_name} (@{me.username})")
                clients.append((phone, client))
            except Exception as e:
                print(f"[{phone}] ❌ Ошибка старта: {e}")

        if not clients:
            print("❌ Нет активных клиентов. Завершение.")
            return

        while True:
            await asyncio.gather(*[self.handle_account(phone, client) for phone, client in clients])
            await asyncio.sleep(LOOP_INTERVAL)

    async def handle_account(self, phone, client):
        """Один цикл обработки аккаунта"""
        try:
            await self.poll_outgoing(phone, client)
            await self.poll_incoming(phone, client)
        except Exception as e:
            print(f"[{phone}] loop error: {e}")

    # === ОТПРАВКА ===
    async def poll_outgoing(self, phone, client):
        """Берём из Django все сообщения delivered=false"""
        try:
            async with self.http.get(f"{DJANGO_BASE}/messages/?delivered=false") as r:
                msgs = await r.json()
        except Exception as e:
            print(f"[{phone}] error fetching outgoing: {e}")
            return

        if not msgs:
            return

        async with self.http.get(f"{DJANGO_BASE}/dialogs/") as r:
            all_dialogs = await r.json()

        for msg in msgs:
            try:
                dlg = next((d for d in all_dialogs if d["id"] == msg["dialog"]), None)
                if not dlg or dlg["account_phone"] != phone:
                    continue

                chat_id = int(dlg["chat_id"])
                text = msg.get("text") or ""

                # --- Если есть медиа ---
                if msg["media"]:
                    for m in msg["media"]:
                        url = f"{DJANGO_BASE}{m['file']}"
                        filename = os.path.basename(m["file"])
                        tmp_path = os.path.join(BASE_DIR, filename)
                        async with self.http.get(url) as rfile:
                            with open(tmp_path, "wb") as f:
                                f.write(await rfile.read())

                        try:
                            if m["media_type"] == "photo":
                                await client.send_photo(chat_id, tmp_path, caption=text)
                            elif m["media_type"] == "video":
                                await client.send_video(chat_id, tmp_path, caption=text)
                            else:
                                await client.send_document(chat_id, tmp_path, caption=text)
                        finally:
                            os.remove(tmp_path)
                else:
                    await client.send_message(chat_id, text)

                # --- После успешной отправки — удаляем сообщение ---
                await self.http.delete(f"{DJANGO_BASE}/messages/{msg['id']}/")
                print(f"[{phone}] ✉️ Отправлено сообщение {msg['id']} в чат {chat_id}")

            except errors.FloodWait as e:
                print(f"[{phone}] FloodWait {e.value}s")
                await asyncio.sleep(e.value)
            except Exception as e:
                print(f"[{phone}] Ошибка отправки {msg['id']}: {e}")

    # === ПРИЁМ ===
    async def poll_incoming(self, phone, client):
        """Собираем историю чатов и добавляем в Django"""
        try:
            async for dialog in client.get_dialogs(limit=20):
                chat = dialog.chat
                chat_title = chat.title or (chat.first_name or "") or str(chat.id)

                # --- Проверяем/создаём диалог в Django ---
                async with self.http.get(f"{DJANGO_BASE}/dialogs/") as r:
                    all_dialogs = await r.json()

                dlg = next(
                    (d for d in all_dialogs if d["account_phone"] == phone and str(d["chat_id"]) == str(chat.id)), None
                )

                if not dlg:
                    payload = {
                        "account_phone": phone,
                        "chat_id": str(chat.id),
                        "chat_title": chat_title,
                    }
                    async with self.http.post(f"{DJANGO_BASE}/dialogs/", data=payload) as resp:
                        if resp.status in (200, 201):
                            dlg = await resp.json()
                        else:
                            print(f"[{phone}] Не удалось создать диалог {chat.id}")
                            continue

                dialog_id = dlg["id"]

                # --- История сообщений ---
                async for msg in client.get_chat_history(chat.id, limit=10):
                    if not (msg.text or msg.media):
                        continue

                    sender = (
                        "Я" if msg.from_user and msg.from_user.is_self
                        else getattr(msg.from_user, "first_name", "Unknown")
                    )

                    files = []
                    if msg.voice or msg.video_note:
                        tmp_path = await client.download_media(msg)
                        files.append({"file_path": tmp_path, "media_type": "voice" if msg.voice else "video_note"})
                    elif msg.photo or msg.video or msg.document:
                        tmp_path = await client.download_media(msg)
                        media_type = (
                            "photo" if msg.photo else "video" if msg.video else "document"
                        )
                        files.append({"file_path": tmp_path, "media_type": media_type})

                    # --- Отправляем в Django ---
                    form = aiohttp.FormData()
                    form.add_field("dialog", str(dialog_id))
                    form.add_field("sender_name", sender)
                    form.add_field("text", msg.text or "")
                    form.add_field("date", msg.date.isoformat())
                    form.add_field("delivered", "true")
                    form.add_field("telegram_id", str(msg.id))

                    for f in files:
                        form.add_field(
                            "files",
                            open(f["file_path"], "rb"),
                            filename=os.path.basename(f["file_path"]),
                            content_type="application/octet-stream",
                        )

                    async with self.http.post(f"{DJANGO_BASE}/messages_media/", data=form) as resp:
                        if resp.status not in (200, 201):
                            print(f"[{phone}] Ошибка создания сообщения {msg.id}: {resp.status}")
                        else:
                            print(f"[{phone}] 💾 Добавлено сообщение {msg.id}")

                    for f in files:
                        try:
                            os.remove(f["file_path"])
                        except:
                            pass

        except Exception as e:
            print(f"[{phone}] poll_incoming error: {e}")

# === ЗАПУСК ===
async def main():
    session_map = load_sessions()
    async with aiohttp.ClientSession() as http:
        worker = TelegramWorker(session_map, http)
        await worker.run_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Остановка вручную.")
