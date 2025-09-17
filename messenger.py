import sys
import os
import requests
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QListWidget, QTextEdit, QPushButton,
    QLabel, QFileDialog, QHBoxLayout, QListWidgetItem, QDialog, QScrollArea
)
from PyQt6.QtGui import QPixmap, QColor
from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

API_BASE = "http://5.129.253.254/api"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class ChatGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Telegram GUI")
        self.resize(1000, 600)

        self.dialogs = []
        self.messages = []
        self.current_dialog_id = None
        self.media_to_send = []

        # --- layout ---
        main_layout = QHBoxLayout(self)

        # список диалогов
        self.dialog_list = QListWidget()
        self.dialog_list.itemClicked.connect(self.open_dialog)
        main_layout.addWidget(self.dialog_list, 1)

        # правая панель
        right_layout = QVBoxLayout()

        self.message_list = QListWidget()
        right_layout.addWidget(self.message_list, 8)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Введите сообщение...")
        right_layout.addWidget(self.text_edit, 1)

        send_layout = QHBoxLayout()
        self.attach_btn = QPushButton("📎 Прикрепить медиа")
        self.attach_btn.clicked.connect(self.attach_media)
        send_layout.addWidget(self.attach_btn)

        self.send_btn = QPushButton("➡ Отправить")
        self.send_btn.clicked.connect(self.send_message)
        send_layout.addWidget(self.send_btn)

        right_layout.addLayout(send_layout)

        # список прикрепленных файлов
        self.attached_files_list = QListWidget()
        right_layout.addWidget(QLabel("Прикрепленные файлы:"))
        right_layout.addWidget(self.attached_files_list, 2)

        main_layout.addLayout(right_layout, 3)

        # таймеры
        self.dialog_timer = QTimer()
        self.dialog_timer.timeout.connect(self.load_dialogs)
        self.dialog_timer.start(5000)

        self.message_timer = QTimer()
        self.message_timer.timeout.connect(self.refresh_current_dialog)
        self.message_timer.start(3000)

        # загрузка диалогов
        self.load_dialogs()

        # медиаплеер (держим в self, чтобы не падал GC)
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

    # === загрузка диалогов ===
    def load_dialogs(self):
        try:
            r = requests.get(f"{API_BASE}/dialogs/")
            r.raise_for_status()
            self.dialogs = r.json()

            self.dialog_list.clear()
            for dlg in self.dialogs:
                last_msg_text = ""
                last_msg_time = ""

                try:
                    r2 = requests.get(f"{API_BASE}/messages/?dialog={dlg['id']}&limit=1")
                    if r2.status_code == 200:
                        msgs = r2.json()
                        if msgs:
                            msg = msgs[-1]  # последнее сообщение
                            last_msg_text = f"{msg['sender_name']}: {msg['text'][:30]}"
                            last_msg_time = msg["date"][11:16]
                except Exception as e:
                    print("Ошибка получения последнего сообщения:", e)

                item_text = f"{dlg['chat_title']} ({dlg['account_phone']})\n{last_msg_text} {last_msg_time}"
                item = QListWidgetItem(item_text)

                if dlg.get("unread_count", 0) > 0:
                    item.setBackground(QColor("#ffffcc"))

                self.dialog_list.addItem(item)
        except Exception as e:
            print("Ошибка загрузки диалогов:", e)

    # === открытие диалога ===
    def open_dialog(self, item):
        index = self.dialog_list.currentRow()
        if 0 <= index < len(self.dialogs):
            self.current_dialog_id = self.dialogs[index]["id"]
            self.load_messages(scroll_to_bottom=True)

    # === загрузка сообщений ===
    def load_messages(self, scroll_to_bottom=False):
        if not self.current_dialog_id:
            return
        try:
            r = requests.get(f"{API_BASE}/messages/?dialog={self.current_dialog_id}")
            r.raise_for_status()
            self.messages = r.json()

            self.message_list.clear()
            for msg in self.messages:
                self.add_message_to_list(msg)

            if scroll_to_bottom:
                self.message_list.scrollToBottom()
        except Exception as e:
            print("Ошибка загрузки сообщений:", e)

    # === обновление активного чата ===
    def refresh_current_dialog(self):
        if not self.current_dialog_id:
            return
        try:
            r = requests.get(f"{API_BASE}/messages/?dialog={self.current_dialog_id}")
            r.raise_for_status()
            new_messages = r.json()

            if len(new_messages) > len(self.messages):
                for msg in new_messages[len(self.messages):]:
                    self.add_message_to_list(msg)
                self.message_list.scrollToBottom()

            self.messages = new_messages
        except Exception as e:
            print("Ошибка автообновления диалога:", e)

    # === сообщение в список ===
    def add_message_to_list(self, msg):
        sender = msg["sender_name"]
        text = msg["text"] or ""
        date = msg["date"][:19].replace("T", " ")
        display_text = f"{sender} [{date}]: {text}"
        item = QListWidgetItem(display_text)
        self.message_list.addItem(item)

        if msg.get("media_file"):
            full_path = os.path.join(BASE_DIR, msg["media_file"])
            if not os.path.exists(full_path):
                return
            btn = QPushButton(f"Открыть {msg['media_type']}: {os.path.basename(full_path)}")
            if msg["media_type"] == "photo":
                btn.clicked.connect(lambda _, p=full_path: self.open_full_image(p))
            elif msg["media_type"] in ["video", "video_note"]:
                btn.clicked.connect(lambda _, p=full_path: self.play_media(p, "video"))
            elif msg["media_type"] == "voice":
                btn.clicked.connect(lambda _, p=full_path: self.play_media(p, "voice"))
            else:
                btn.clicked.connect(lambda _, p=full_path: os.startfile(p))
            list_item = QListWidgetItem()
            self.message_list.addItem(list_item)
            self.message_list.setItemWidget(list_item, btn)

    # === открыть фото ===
    def open_full_image(self, file_path):
        dialog = QDialog(self)
        dialog.setWindowTitle("Изображение")
        layout = QVBoxLayout(dialog)
        scroll = QScrollArea()
        label = QLabel()
        pixmap = QPixmap(file_path)
        label.setPixmap(pixmap)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setWidget(label)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
        dialog.exec()

    # === воспроизведение медиа ===
    def play_media(self, file_path, media_type):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Воспроизведение {media_type}")
        layout = QVBoxLayout(dialog)
        if media_type in ["video", "video_note"]:
            video_widget = QVideoWidget()
            layout.addWidget(video_widget)
            self.player.setVideoOutput(video_widget)
        self.player.setSource(QUrl.fromLocalFile(file_path))
        self.player.play()
        dialog.exec()
        self.player.stop()

    # === прикрепить медиа ===
    def attach_media(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Выберите файлы")
        if files:
            self.media_to_send.extend(files)
            self.attached_files_list.clear()
            for f in self.media_to_send:
                self.attached_files_list.addItem(os.path.basename(f))

    # === отправка ===
    def send_message(self):
        if not self.current_dialog_id:
            return
        text = self.text_edit.toPlainText()
        if not text and not self.media_to_send:
            return
        try:
            for mf in self.media_to_send or [None]:
                media_file = None
                media_type = None
                if mf:
                    media_file = os.path.relpath(mf, BASE_DIR)
                    ext = os.path.splitext(mf)[1].lower()
                    if ext in [".jpg", ".jpeg", ".png"]:
                        media_type = "photo"
                    elif ext in [".mp4"]:
                        media_type = "video"
                    elif ext in [".ogg"]:
                        media_type = "voice"
                    else:
                        media_type = "document"

                payload = {
                    "dialog": self.current_dialog_id,
                    "sender_name": "Я",
                    "text": text if mf is None else "",
                    "date": datetime.now().isoformat(),
                    "media_file": media_file,
                    "media_type": media_type,
                    "delivered": False,
                }
                r = requests.post(f"{API_BASE}/messages/", json=payload)
                if r.status_code not in (200, 201):
                    print("Ошибка отправки:", r.text)

            self.text_edit.clear()
            self.media_to_send.clear()
            self.attached_files_list.clear()
            self.load_messages(scroll_to_bottom=True)
        except Exception as e:
            print("Ошибка отправки:", e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ChatGUI()
    gui.show()
    sys.exit(app.exec())
