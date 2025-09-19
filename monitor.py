import asyncio
import os
import tempfile
from datetime import datetime
import requests
from pyrogram import Client
from pyrogram.errors import FloodWait
from pyrogram.types import InputMediaDocument, InputMediaVideo, InputMediaPhoto

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

def create_message(dialog_id, sender_name, text, date_iso, delivered=True, telegram_id=None):
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
        "delivered": delivered,
        "telegram_id": telegram_id
    }
    try:
        r = requests.post(f"{API_BASE}/messages/", json=payload)
        if r.status_code in (200, 201):
            return r.json()
        else:
            print("create_message failed:", r.status_code, r.text)
            return False
    except Exception as e:
        print("create_message error:", e)
        return False

def mark_delivered(message_id,new_id):
    try:
        requests.delete(f"{API_BASE}/messages/{message_id}/", json={"delivered": True,'created_id':new_id})
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

    def get_input_media(self,file_path, caption=None):
        """Определяем тип медиа по расширению"""
        ext = file_path.lower().split(".")[-1]
        if ext in ["jpg", "jpeg", "png", "gif", "webp"]:
            return InputMediaPhoto(file_path, caption=caption)
        elif ext in ["mp4", "mov", "avi", "mkv"]:
            return InputMediaVideo(file_path, caption=caption)
        else:
            return InputMediaDocument(file_path, caption=caption)

    async def _extract_media_from_msg(self, msg):
        """
        Вспомогательная функция: извлекает медиа из одного сообщения
        """
        media_list = []
        try:
            if msg.photo:
                file_path = await self.client.download_media(msg, file_name=None)
                media_list.append({"file_path": file_path, "media_type": "photo"})
            elif msg.video:
                file_path = await self.client.download_media(msg, file_name=None)
                media_list.append({"file_path": file_path, "media_type": "video"})
            elif msg.voice:
                file_path = await self.client.download_media(msg, file_name=None)
                media_list.append({"file_path": file_path, "media_type": "voice"})
            elif msg.video_note:
                file_path = await self.client.download_media(msg, file_name=None)
                media_list.append({"file_path": file_path, "media_type": "video_note"})
            elif msg.document:
                file_path = await self.client.download_media(msg, file_name=None)
                media_list.append({"file_path": file_path, "media_type": "document"})
        except Exception as e:
            print(f"Ошибка скачивания медиа для msg {msg.id}: {e}")
        return media_list
    async def get_media_files(self, msg):
        """
        Получает список медиа-файлов из сообщения или альбома.
        client: pyrogram.Client
        msg: pyrogram.types.Message
        Возвращает список словарей {"file_path": ..., "media_type": ...}
        """
        media_list = []

        # --- Если сообщение часть альбома ---
        if msg.media_group_id:
            # Получаем все сообщения в этом альбоме
            album_msgs = [m async for m in self.client.get_chat_history(msg.chat.id, limit=100)
                          if m.media_group_id == msg.media_group_id]

            for m in album_msgs:
                media_list.extend(await self._extract_media_from_msg(m))
        else:
            media_list.extend(await self._extract_media_from_msg(msg))

        return media_list

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

                            if msg['media']:
                                media_files = list(msg['media'])

                                if len(media_files) == 1:
                                    # Один файл → отправляем как фото/видео/документ
                                    mf = media_files[0]
                                    media = self.get_input_media(mf['file'], caption=msg['text'] or "")
                                    print(f"http://5.129.253.254{mf['file']}")

                                    url = f"http://5.129.253.254{mf['file']}"

                                    # Скачиваем файл во временный
                                    r = requests.get(url, stream=True)
                                    if r.status_code != 200:
                                        print(f"Не удалось скачать файл {url}")
                                        continue

                                    suffix = os.path.splitext(url)[-1]
                                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                                        for chunk in r.iter_content(1024):
                                            tmp.write(chunk)
                                        tmp_path = tmp.name
                                    if isinstance(media, InputMediaPhoto):
                                        await self.client.send_photo(chat_id, tmp_path,
                                                                caption=msg['text'] or "")
                                    elif isinstance(media, InputMediaVideo):
                                        await self.client.send_video(chat_id, tmp_path,
                                                                caption=msg['text'] or "")
                                    else:
                                        await self.client.send_document(chat_id, tmp_path,
                                                                   caption=msg['text'] or "")
                                else:
                                    # Несколько файлов → альбом
                                    # media_group = []
                                    tmp_files = []
                                    photos = []
                                    videos = []
                                    documents = []
                                    for i, mf in enumerate(media_files):
                                        caption = msg['text'] if i == 0 else None
                                        print(f"http://5.129.253.254{mf['file']}")

                                        url = f"http://5.129.253.254{mf['file']}"

                                        # Скачиваем файл во временный
                                        r = requests.get(url, stream=True)
                                        if r.status_code != 200:
                                            print(f"Не удалось скачать файл {url}")
                                            continue

                                        suffix = os.path.splitext(url)[-1]
                                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                                            for chunk in r.iter_content(1024):
                                                tmp.write(chunk)
                                            tmp.close()
                                            tmp_files.append(tmp.name)
                                        ext = tmp.name.lower().split(".")[-1]
                                        if ext in ["jpg", "jpeg", "png", "gif", "webp"]:
                                            photos.append(self.get_input_media(tmp.name, caption=caption))  # подпись только к первому
                                        elif ext in ["mp4", "mov", "avi", "mkv"]:
                                            videos.append(self.get_input_media(tmp.name, caption=caption))
                                        else:
                                            documents.append(self.get_input_media(tmp.name, caption=caption))

                                        # media_group.append(self.get_input_media(tmp.name, caption=caption))
                                    # print(media_group)
                                    for media_group in [photos,videos]:
                                        # print(f'{media_group} - {len(media_group)}')
                                        if len(media_group) != 0:
                                            await self.client.send_media_group(chat_id, media_group)
                                    for doc in documents:
                                        await self.client.send_document(chat_id,doc.media)
                            else:
                                # Только текст
                                await self.client.send_message(chat_id, msg['text'] or "")

                            # Помечаем как доставленное
                            mark_delivered(msg["id"], None)
                            print(f"[{self.phone}] sent message {msg['id']} to chat {chat_id}")
                        except FloodWait as e:
                            wait = int(e.value) + 1
                            print(f"[{self.phone}] FloodWait {wait}s while sending, sleeping...")
                            await asyncio.sleep(wait)
                        except Exception as e:
                            print(f"[{self.phone}] Send error for message {msg.get('id')}: {e}")


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

                        files = await self.get_media_files(msg)
                        for f in files:
                            print(f"Файл: {f['file_path']}, тип: {f['media_type']}")

                        # Создаём сообщение в Django (отмечаем как delivered=True т.к. это сообщение из Telegram)
                        created = create_message(dialog_id, sender, text, date_iso,
                                                 delivered=True, telegram_id=getattr(msg, "id", None))
                        if created != False:
                            print(f"[{self.phone}] created message in API dialog={dialog_id}, tg_id={getattr(msg,'id',None)}")
                            # undelivered = get_undelivered_messages_for_account(self.phone)
                            # if undelivered:
                            #     print(f"[{self.phone}] найдено {len(undelivered)} недоставленных, ищем нужное подставляем медиа")
                            # for msg in undelivered:
                            #     if msg['dialog'] == dialog_id:
                            #         if msg['text'] == text and msg['sender'] == sender:
                            #             mark_delivered(msg,created['id'])
                            #             print("Пометили с переносом текста..")
                            #             break
                except FloodWait as e:
                    wait = int(e.value) + 1
                    print(f"[{self.phone}] FloodWait {wait}s while fetching history for chat {chat_id}, sleeping...")
                    await asyncio.sleep(wait)
                except Exception as e:
                    print(f"[{self.phone}] history loop error for chat {chat_id}: {e}")



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
