import asyncio
import os
from datetime import datetime
import requests
from pyrogram import Client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
MEDIA_DIR = os.path.join(BASE_DIR, "tgserver/media")
os.makedirs(MEDIA_DIR, exist_ok=True)

API_FILE = os.path.join(BASE_DIR, "api.txt")
ACCOUNTS_FILE = os.path.join(BASE_DIR, "accounts.txt")
API_BASE = "http://5.129.253.254/api"

# --- API ID / HASH ---
with open(API_FILE) as f:
    API_ID = int(f.readline().strip())
    API_HASH = f.readline().strip()

# --- Номера аккаунтов ---
with open(ACCOUNTS_FILE) as f:
    ACCOUNTS = [line.strip() for line in f if line.strip()]

# --- API функции ---
def find_dialog(account_phone, chat_id):
    try:
        r = requests.get(f"{API_BASE}/dialogs/")
        r.raise_for_status()
        for dlg in r.json():
            if dlg["account_phone"] == account_phone and int(dlg["chat_id"]) == int(chat_id):
                return dlg
    except:
        pass
    return None

def create_dialog(account_phone, chat_id, chat_title):
    existing = find_dialog(account_phone, chat_id)
    if existing:
        return existing["id"]
    r = requests.post(f"{API_BASE}/dialogs/", json={
        "account_phone": account_phone,
        "chat_id": chat_id,
        "chat_title": chat_title
    })
    if r.status_code in (200, 201):
        return r.json()["id"]
    return None

def get_undelivered_messages(account_phone):
    try:
        r = requests.get(f"{API_BASE}/messages/?delivered=false")
        r.raise_for_status()
        msgs = []
        for msg in r.json():
            dlg_resp = requests.get(f"{API_BASE}/dialogs/{msg['dialog']}/").json()
            # dlg_resp может быть списком
            if isinstance(dlg_resp, list):
                dlg_resp = dlg_resp[0]
            if dlg_resp["account_phone"] == account_phone:
                msgs.append(msg)
        return msgs
    except:
        return []

def create_or_update_message(dialog_id, sender_name, text, date_iso,
                             media_file=None, media_type=None,
                             delivered=True, telegram_id=None, account_phone=None):
    """
    Создаём или обновляем сообщение по telegram_id + account_phone.
    """
    if telegram_id is not None:
        try:
            r = requests.get(f"{API_BASE}/messages/?dialog={dialog_id}&telegram_id={telegram_id}&account_phone={account_phone}")
            r.raise_for_status()
            existing = r.json()
            if existing:
                # обновляем запись (например, если GUI поставил delivered=False)
                msg_id = existing[0]["id"]
                requests.patch(f"{API_BASE}/messages/{msg_id}/", json={"delivered": delivered})
                return False
        except:
            pass

    payload = {
        "dialog": dialog_id,
        "sender_name": sender_name,
        "text": text,
        "date": date_iso,
        "media_file": media_file,
        "media_type": media_type,
        "delivered": delivered,
        "telegram_id": telegram_id,
        "account_phone": account_phone
    }
    try:
        r = requests.post(f"{API_BASE}/messages/", json=payload)
        return r.status_code in (200, 201)
    except Exception as e:
        print("Create message error:", e)
        return False

def mark_delivered(message_id):
    try:
        requests.patch(f"{API_BASE}/messages/{message_id}/", json={"delivered": True})
    except:
        pass

# --- Монитор аккаунта ---
class AccountMonitor:
    def __init__(self, phone):
        self.phone = phone
        self.client = Client(
            phone.replace("+", ""),
            api_id=API_ID,
            api_hash=API_HASH,
            workdir=SESSIONS_DIR
        )

    async def start(self):
        await self.client.start()
        print(f"[{self.phone}] started")

    async def stop(self):
        await self.client.stop()

    async def scan_once(self):
        try:
            async for dialog in self.client.get_dialogs(limit=50):
                chat = dialog.chat
                chat_id = chat.id
                chat_title = chat.title or (chat.first_name or "") + (chat.last_name or "") or str(chat_id)
                dialog_id = create_dialog(self.phone, chat_id, chat_title)
                if not dialog_id:
                    continue

                # Отметка прочитанного
                try:
                    await self.client.read_chat_history(chat_id)
                except Exception as e:
                    print(f"[{self.phone}] Ошибка отметки прочитанного: {e}")

                # История сообщений
                async for msg in self.client.get_chat_history(chat_id, limit=50):
                    # Не обрабатываем собственные сообщения (GUI создаёт их)
                    if msg.from_user and msg.from_user.is_self:
                        continue

                    date_iso = msg.date.isoformat()
                    sender = msg.from_user.first_name if msg.from_user else "Unknown"
                    text = msg.text or ""

                    media_file = None
                    media_type = None

                    try:
                        if msg.photo:
                            media_type = "photo"
                            file_path = os.path.join(MEDIA_DIR, f"{msg.id}_photo.jpg")
                        elif msg.video:
                            media_type = "video"
                            file_path = os.path.join(MEDIA_DIR, f"{msg.id}_video.mp4")
                        elif msg.voice:
                            media_type = "voice"
                            file_path = os.path.join(MEDIA_DIR, f"{msg.id}_voice.ogg")
                        elif msg.video_note:
                            media_type = "video_note"
                            file_path = os.path.join(MEDIA_DIR, f"{msg.id}_video_note.mp4")
                        elif msg.document:
                            media_type = "document"
                            name = msg.document.file_name or f"{msg.id}_doc"
                            file_path = os.path.join(MEDIA_DIR, name)
                        else:
                            file_path = None

                        if file_path and not os.path.exists(file_path):
                            await self.client.download_media(msg, file_name=file_path)
                        if file_path:
                            media_file = os.path.relpath(file_path, BASE_DIR)
                    except Exception as e:
                        print(f"[{self.phone}] Download media error msg {msg.id}: {e}")

                    create_or_update_message(
                        dialog_id,
                        sender,
                        text,
                        date_iso,
                        media_file,
                        media_type,
                        delivered=True,
                        telegram_id=msg.id,
                        account_phone=self.phone
                    )

            # --- отправка сообщений из GUI ---
            undelivered = get_undelivered_messages(self.phone)
            for msg in undelivered:
                try:
                    dlg_resp = requests.get(f"{API_BASE}/dialogs/{msg['dialog']}/").json()
                    if isinstance(dlg_resp, list):
                        dlg_resp = dlg_resp[0]
                    chat_id = dlg_resp["chat_id"]

                    if msg.get("media_file") and msg.get("media_type"):
                        mt = msg["media_type"]
                        mf = os.path.join(BASE_DIR, msg["media_file"])
                        if mt == "photo":
                            await self.client.send_photo(chat_id, mf)
                        elif mt == "video":
                            await self.client.send_video(chat_id, mf)
                        elif mt == "voice":
                            await self.client.send_voice(chat_id, mf)
                        elif mt == "video_note":
                            await self.client.send_video_note(chat_id, mf)
                        elif mt == "document":
                            await self.client.send_document(chat_id, mf)
                    else:
                        await self.client.send_message(chat_id, msg["text"])

                    # После отправки обновляем запись
                    requests.patch(f"{API_BASE}/messages/{msg['id']}/", json={
                        "delivered": True,
                        "telegram_id": msg.get("telegram_id", 0)  # обновить telegram_id, если нужно
                    })
                    print(f"[{self.phone}] отправлено сообщение {msg['id']} -> delivered")
                except Exception as e:
                    print(f"[{self.phone}] Send error:", e)

        except Exception as e:
            print(f"[{self.phone}] scan error:", e)


async def run_loop():
    monitors = [AccountMonitor(p) for p in ACCOUNTS]
    for m in monitors:
        await m.start()
    try:
        while True:
            tasks = [m.scan_once() for m in monitors]
            await asyncio.gather(*tasks)
            await asyncio.sleep(3)
    finally:
        for m in monitors:
            await m.stop()


if __name__ == "__main__":
    asyncio.run(run_loop())
