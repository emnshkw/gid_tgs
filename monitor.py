import asyncio
import os
from datetime import datetime
import requests
from pyrogram import Client
from pyrogram.errors import FloodWait

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
with open(ACCOUNTS_FILE, encoding="utf-8") as f:
    ACCOUNTS = [line.strip() for line in f if line.strip()]

# --- Вспомогательные API-функции (Django REST) ---
def find_dialog(account_phone, chat_id):
    """Ищем существующий диалог в Django по номеру аккаунта и chat_id."""
    try:
        r = requests.get(f"{API_BASE}/dialogs/")
        r.raise_for_status()
        for dlg in r.json():
            try:
                if dlg.get("account_phone") == account_phone and int(dlg.get("chat_id")) == int(chat_id):
                    return dlg
            except Exception:
                continue
    except Exception as e:
        print("find_dialog error:", e)
    return None

def create_dialog(account_phone, chat_id, chat_title):
    """Создаёт диалог через API, если его ещё нет."""
    existing = find_dialog(account_phone, chat_id)
    if existing:
        return existing["id"]
    try:
        payload = {
            "account_phone": account_phone,
            "chat_id": str(chat_id),
            "chat_title": chat_title
        }
        r = requests.post(f"{API_BASE}/dialogs/", json=payload)
        if r.status_code in (200, 201):
            print(f"[{account_phone}] Создан диалог {chat_title} ({chat_id}) -> id {r.json().get('id')}")
            return r.json().get("id")
        else:
            print(f"[{account_phone}] Ошибка create_dialog: {r.status_code} {r.text}")
    except Exception as e:
        print("create_dialog error:", e)
    return None

def get_undelivered_messages_for_account(account_phone):
    """
    Берём все сообщения delivered=false и фильтруем те, которые привязаны к этому аккаунту.
    Возвращаем список сообщений (json).
    """
    try:
        r = requests.get(f"{API_BASE}/messages/?delivered=false")
        r.raise_for_status()
        msgs = []
        for msg in r.json():
            try:
                dlg = requests.get(f"{API_BASE}/dialogs/{msg['dialog']}/").json()
                for d in dlg:
                    if d['id'] == msg['dialog']:
                        dlg = d
                        if dlg["account_phone"] == account_phone:
                            msgs.append(msg)
            except Exception:
                continue
        return msgs
    except Exception as e:
        print("get_undelivered_messages_for_account error:", e)
        return []

def create_message(dialog_id, sender_name, text, date_iso,
                   media_file=None, media_type=None, delivered=True, telegram_id=None):
    """
    Создаём сообщение через API.
    Если передан telegram_id — проверяем уникальность (dialog + telegram_id).
    media_file хранится как относительный путь от BASE_DIR.
    """
    try:
        if telegram_id is not None:
            q = f"{API_BASE}/messages/?dialog={dialog_id}&telegram_id={telegram_id}"
            rchk = requests.get(q)
            rchk.raise_for_status()
            if rchk.json():
                if text == 'пидор':
                    print(q)
                    print(rchk.json())
                # Уже есть сообщение с таким telegram_id в этом диалоге
                return False
    except Exception:
        # если проверка упала — продолжим попытку создания (без стопа)
        pass

    payload = {
        "dialog": dialog_id,
        "sender_name": sender_name,
        "text": text or "",
        "date": date_iso,
        "media_file": media_file,
        "media_type": media_type,
        "delivered": delivered,
        "telegram_id": telegram_id
    }
    try:
        r = requests.post(f"{API_BASE}/messages/", json=payload)
        if text == 'пидор':
            try:
                print(r.json())
            except:
                pass
        if r.status_code in (200, 201):
            return r.json()
        else:
            print("create_message failed:", r.status_code, r.text)
            return False
    except Exception as e:
        print("create_message error:", e)
        return False

def mark_delivered(message_id,created):
    try:
        requests.delete(f"{API_BASE}/messages/{message_id}/", json={"delivered": True,'created':created})
        print(f"Marked delivered: {message_id}")
    except Exception as e:
        print("mark_delivered error:", e)

# --- Монитор для одного аккаунта ---
class AccountMonitor:
    def __init__(self, phone):
        """
        phone должен быть в формате с '+' (тот, что в accounts.txt).
        Сессии в папке sessions хранятся без '+' — используем phone.replace("+","") как имя сессии.
        """
        self.phone = phone
        session_name = phone.replace("+", "")
        self.client = Client(session_name, api_id=API_ID, api_hash=API_HASH, workdir=SESSIONS_DIR)
        self.seen_messages = set()  # локальный кэш id сообщений, чтобы не пересоздавать много раз
        self.account_user_id = None

    async def start(self):
        await self.client.start()
        me = await self.client.get_me()
        self.account_user_id = me.id
        print(f"[{self.phone}] client started as {me.first_name} ({self.account_user_id})")

    async def stop(self):
        try:
            await self.client.stop()
        except Exception:
            pass
        print(f"[{self.phone}] client stopped")

    async def scan_once(self):
        try:
            # Проходим по диалогам (limit ограничивает количество)
            async for dialog in self.client.get_dialogs(limit=0):
                chat = dialog.chat
                chat_id = chat.id
                # Сформируем читабельное название чата
                chat_title = chat.title or ((chat.first_name or "") + (" " + chat.last_name if chat.last_name else "")) or str(chat_id)
                dialog_id = create_dialog(self.phone, chat_id, chat_title)
                if not dialog_id:
                    continue

                # Получаем историю (не очень большой лимит чтобы не получать FloodWait)
                try:
                    async for msg in self.client.get_chat_history(chat_id, limit=0):
                        # Пропускаем системные пустые сообщения
                        if not getattr(msg, "text", None) and not (getattr(msg, "media", None) or getattr(msg, "photo", None) or getattr(msg, "document", None)):
                            continue

                        # предотвращаем повторную обработку в рамках этого процесса
                        unique_key = f"{self.phone}:{msg.id}"
                        if unique_key in self.seen_messages:
                            continue
                        self.seen_messages.add(unique_key)

                        # Подготовка полей
                        date_iso = msg.date.isoformat()
                        if getattr(msg, "from_user", None) and getattr(msg.from_user, "is_self", False):
                            sender = "Я"
                        elif getattr(msg, "from_user", None):
                            sender = getattr(msg.from_user, "first_name", "Unknown")
                        else:
                            sender = "Unknown"
                        text = getattr(msg, "text", "") or ""

                        media_file = None
                        media_type = None

                        # Определяем тип медиа и путь
                        try:
                            if getattr(msg, "photo", None):
                                media_type = "photo"
                                filename = f"{self.phone.replace('+','')}_{msg.id}_photo.jpg"
                                file_path = os.path.join(MEDIA_DIR, filename)
                            elif getattr(msg, "video", None):
                                media_type = "video"
                                filename = f"{self.phone.replace('+','')}_{msg.id}_video.mp4"
                                file_path = os.path.join(MEDIA_DIR, filename)
                            elif getattr(msg, "voice", None):
                                media_type = "voice"
                                filename = f"{self.phone.replace('+','')}_{msg.id}_voice.ogg"
                                file_path = os.path.join(MEDIA_DIR, filename)
                            elif getattr(msg, "video_note", None):
                                media_type = "video_note"
                                filename = f"{self.phone.replace('+','')}_{msg.id}_video_note.mp4"
                                file_path = os.path.join(MEDIA_DIR, filename)
                            elif getattr(msg, "document", None):
                                media_type = "document"
                                name = msg.document.file_name or f"{self.phone.replace('+','')}_{msg.id}_doc"
                                filename = f"{self.phone.replace('+','')}_{name}"
                                file_path = os.path.join(MEDIA_DIR, filename)
                            else:
                                file_path = None

                            if file_path:
                                if not os.path.exists(file_path):
                                    try:
                                        await self.client.download_media(msg, file_name=file_path)
                                        print(f"[{self.phone}] downloaded media for msg {msg.id} -> {file_path}")
                                    except Exception as e:
                                        print(f"[{self.phone}] download_media error for msg {msg.id}: {e}")
                                        file_path = None
                                if file_path:
                                    # сохраняем относительный путь от BASE_DIR
                                    media_file = os.path.relpath(file_path, BASE_DIR)
                        except Exception as e:
                            print(f"[{self.phone}] media processing error msg {getattr(msg,'id',None)}: {e}")

                        # Создаём сообщение в Django (отмечаем как delivered=True т.к. это сообщение из Telegram)
                        print(msg)
                        created = create_message(dialog_id, sender, text, date_iso,
                                                 media_file=media_file, media_type=media_type,
                                                 delivered=True, telegram_id=getattr(msg, "id", None))
                        if created != False:
                            print(f"[{self.phone}] created message in API dialog={dialog_id}, tg_id={getattr(msg,'id',None)}")
                except FloodWait as e:
                    wait = int(e.value) + 1
                    print(f"[{self.phone}] FloodWait {wait}s while fetching history for chat {chat_id}, sleeping...")
                    await asyncio.sleep(wait)
                except Exception as e:
                    print(f"[{self.phone}] history loop error for chat {chat_id}: {e}")

            # --- Отправка сообщений из Django для этого аккаунта ---
            undelivered = get_undelivered_messages_for_account(self.phone)
            if undelivered:
                print(f"[{self.phone}] found {len(undelivered)} undelivered messages to send")
            for msg in undelivered:
                try:
                    # Получаем диалог, чтобы узнать chat_id
                    try:
                        dlg_resp = requests.get(f"{API_BASE}/dialogs/{msg['dialog']}/")

                        dlg_resp.raise_for_status()
                        dlg = dlg_resp.json()
                        for d in dlg:
                            if d['id'] == msg['dialog']:
                                chat_id = d["chat_id"]
                                break
                    except Exception as e:
                        print(f"[{self.phone}] cannot fetch dialog {msg.get('dialog')}: {e}")
                        continue

                    # Полный путь к файлу, если задан
                    if msg.get("media_file") and msg.get("media_type"):
                        mt = msg["media_type"]
                        # media_file хранится как относительный путь от BASE_DIR
                        mf = os.path.join(BASE_DIR, msg["media_file"])
                        if mt == "photo":
                            await self.client.send_photo(chat_id, mf, caption=msg.get("text") or None)
                        elif mt == "video":
                            await self.client.send_video(chat_id, mf, caption=msg.get("text") or None)
                        elif mt == "voice":
                            await self.client.send_voice(chat_id, mf)
                        elif mt == "video_note":
                            await self.client.send_video_note(chat_id, mf)
                        elif mt == "document":
                            await self.client.send_document(chat_id, mf, caption=msg.get("text") or None)
                        else:
                            # fallback: отправим как документ
                            await self.client.send_document(chat_id, mf, caption=msg.get("text") or None)
                    else:
                        await self.client.send_message(chat_id, msg.get("text") or "")

                    # Помечаем как доставленное
                    try:
                        mark_delivered(msg["id"],created)
                    except:
                        pass
                    print(f"[{self.phone}] sent message {msg['id']} to chat {chat_id}")
                except FloodWait as e:
                    wait = int(e.value) + 1
                    print(f"[{self.phone}] FloodWait {wait}s while sending, sleeping...")
                    await asyncio.sleep(wait)
                except Exception as e:
                    print(f"[{self.phone}] Send error for message {msg.get('id')}: {e}")

        except Exception as e:
            print(f"[{self.phone}] scan error:", e)


# --- Главный цикл ---
async def run_loop():
    monitors = [AccountMonitor(phone) for phone in ACCOUNTS]
    # старт всех клиентов
    for m in monitors:
        try:
            await m.start()
        except Exception as e:
            print(f"Failed to start monitor for {m.phone}: {e}")

    try:
        while True:
            tasks = [m.scan_once() for m in monitors]
            # параллельно запускаем сканы
            await asyncio.gather(*tasks)
            await asyncio.sleep(3)
    except KeyboardInterrupt:
        print("Stopping monitors...")
    finally:
        for m in monitors:
            try:
                await m.stop()
            except Exception:
                pass

if __name__ == "__main__":
    asyncio.run(run_loop())
