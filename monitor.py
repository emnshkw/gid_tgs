import sys
import os
import requests
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QListWidget, QTextEdit, QPushButton, QLabel,
    QFileDialog, QHBoxLayout, QListWidgetItem, QDialog, QScrollArea
)
from PyQt6.QtGui import QPixmap, QColor
from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

API_BASE = "http://127.0.0.1:8000/api"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class ChatGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Telegram GUI")
        self.resize(1000, 600)
        self.dialogs = []
        self.messages = []
        self.current_dialog_id = None
        self.media_to_send = None

        main_layout = QHBoxLayout()
        self.setLayout(main_layout)

        # --- Список диалогов ---
        self.dialog_list = QListWidget()
        self.dialog_list.itemClicked.connect(self.open_dialog)
        main_layout.addWidget(self.dialog_list, 1)

        # --- Панель сообщений ---
        right_layout = QVBoxLayout()
        self.message_list = QListWidget()
        right_layout.addWidget(self.message_list, 8)

        self.text_edit = QTextEdit()
        right_layout.addWidget(self.text_edit, 1)

        send_layout = QHBoxLayout()
        self.attach_btn = QPushButton("Прикрепить медиа")
        self.attach_btn.clicked.connect(self.attach_media)
        send_layout.addWidget(self.attach_btn)

        self.send_btn = QPushButton("Отправить")
        self.send_btn.clicked.connect(self.send_message)
        send_layout.addWidget(self.send_btn)

        right_layout.addLayout(send_layout)
        main_layout.addLayout(right_layout, 3)

        # --- Таймеры автообновления ---
        self.dialogs_timer = QTimer()
        self.dialogs_timer.timeout.connect(self.load_dialogs)
        self.dialogs_timer.start(5000)  # обновление списка диалогов каждые 5 секунд

        self.dialog_refresh_timer = QTimer()
        self.dialog_refresh_timer.timeout.connect(self.refresh_current_dialog)
        self.dialog_refresh_timer.start(3000)  # обновление открытого диалога каждые 3 секунды

        self.load_dialogs()

    # --- Загрузка диалогов ---
    def load_dialogs(self):
        try:
            r = requests.get(f"{API_BASE}/dialogs/")
            r.raise_for_status()
            self.dialogs = r.json()
            self.dialog_list.clear()
            for dlg in self.dialogs:
                last_msg_text = ""
                last_msg_date = ""
                try:
                    r2 = requests.get(f"{API_BASE}/messages/?dialog={dlg['id']}&limit=0")
                    if r2.status_code == 200 and r2.json():
                        msg = r2.json()[-1]
                        last_msg_text = f"{msg['sender_name']}: {msg['text'][:50]}"
                        last_msg_date = msg['date'][:19].replace("T", " ")
                except Exception as e:
                    print("Ошибка получения последнего сообщения:", e)

                item_text = f"{dlg['chat_title']} ({dlg['account_phone']})\n{last_msg_text} [{last_msg_date}]"
                item = QListWidgetItem(item_text)
                if dlg.get("unread_count", 0) > 0:
                    item.setBackground(QColor("#ffffcc"))
                self.dialog_list.addItem(item)
        except Exception as e:
            print("Ошибка загрузки диалогов:", e)

    # --- Обновление последнего сообщения в списке диалогов ---
    def update_last_message_in_dialog_list(self, dialog_id, sender_name, text, date_str):
        for i, dlg in enumerate(self.dialogs):
            if dlg["id"] == dialog_id:
                last_msg = f"{sender_name}: {text[:50]} [{date_str[:19].replace('T', ' ')}]"
                item = self.dialog_list.item(i)
                item.setText(f"{dlg['chat_title']} ({dlg['account_phone']})\n{last_msg}")
                break

    # --- Открытие диалога ---
    def open_dialog(self, item):
        self.load_messages(item, scroll_to_bottom=True)

    # --- Загрузка сообщений ---
    def load_messages(self, item, scroll_to_bottom=False):
        index = self.dialog_list.currentRow()
        if index < 0 or index >= len(self.dialogs):
            return
        dlg = self.dialogs[index]
        self.current_dialog_id = dlg["id"]
        try:
            r = requests.get(f"{API_BASE}/messages/?dialog={self.current_dialog_id}")
            r.raise_for_status()
            self.messages = r.json()

            scroll_pos = self.message_list.verticalScrollBar().value()
            self.message_list.clear()
            for msg in self.messages:
                self.add_message_to_list(msg)

            # Обновляем последнее сообщение в списке диалогов
            if self.messages:
                last_msg = self.messages[-1]
                self.update_last_message_in_dialog_list(
                    last_msg["dialog"], last_msg["sender_name"], last_msg["text"], last_msg["date"]
                )

            # Скролл вниз при открытии диалога
            if scroll_to_bottom:
                self.message_list.scrollToBottom()
            else:
                self.message_list.verticalScrollBar().setValue(scroll_pos)

        except Exception as e:
            print("Ошибка загрузки сообщений:", e)

    # --- Автообновление открытого диалога ---
    def refresh_current_dialog(self):
        if self.current_dialog_id:
            self.load_messages(self.dialog_list.currentItem(), scroll_to_bottom=False)

    # --- Добавление сообщения в QListWidget ---
    def add_message_to_list(self, msg):
        sender = msg["sender_name"]
        text = msg["text"]
        date = msg["date"][:19].replace("T", " ")
        display_text = f"{sender} [{date}]: {text}"
        item = QListWidgetItem(display_text)
        self.message_list.addItem(item)

        # Медиа
        if msg.get("media_file"):
            full_path = os.path.join(BASE_DIR, msg["media_file"])
            if not os.path.exists(full_path):
                return
            if msg["media_type"] == "photo":
                btn = QPushButton(f"Открыть изображение: {os.path.basename(full_path)}")
                btn.clicked.connect(lambda checked, p=full_path: self.open_full_image(p))
            elif msg["media_type"] in ["video", "video_note"]:
                btn = QPushButton(f"Воспроизвести {msg['media_type']}: {os.path.basename(full_path)}")
                btn.clicked.connect(lambda checked, p=full_path, t=msg["media_type"]: self.play_media(p, t))
            elif msg["media_type"] == "voice":
                btn = QPushButton(f"Воспроизвести голосовое: {os.path.basename(full_path)}")
                btn.clicked.connect(lambda checked, p=full_path: self.play_media(p, "voice"))
            else:  # документы
                btn = QPushButton(f"Открыть файл: {os.path.basename(full_path)}")
                btn.clicked.connect(lambda checked, p=full_path: os.startfile(p))
            list_item = QListWidgetItem()
            self.message_list.addItem(list_item)
            self.message_list.setItemWidget(list_item, btn)

    # --- Фото на весь экран ---
    def open_full_image(self, file_path):
        dialog = QDialog(self)
        dialog.setWindowTitle("Изображение")
        dialog.setWindowState(Qt.WindowState.WindowMaximized)
        layout = QVBoxLayout(dialog)
        scroll = QScrollArea()
        label = QLabel()
        pixmap = QPixmap(file_path)
        label.setPixmap(pixmap)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setScaledContents(True)
        scroll.setWidget(label)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
        dialog.exec()

    # --- Воспроизведение медиа ---
    def play_media(self, file_path, media_type):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Воспроизведение {media_type}")
        dialog.resize(800, 600)
        layout = QVBoxLayout(dialog)
        audio_output = QAudioOutput()
        dialog.audio_output = audio_output
        player = QMediaPlayer()
        player.setAudioOutput(audio_output)
        dialog.player = player

        if media_type in ["video", "video_note"]:
            video_widget = QVideoWidget()
            layout.addWidget(video_widget)
            player.setVideoOutput(video_widget)
            player.setSource(QUrl.fromLocalFile(file_path))
            player.play()
        elif media_type == "voice":
            player.setSource(QUrl.fromLocalFile(file_path))
            player.play()

        dialog.show()
        dialog.finished.connect(player.stop)

    # --- Прикрепление медиа ---
    def attach_media(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите медиа")
        if file_path:
            self.media_to_send = file_path
            print("Прикреплено:", file_path)

    # --- Отправка сообщения ---
    def send_message(self):
        if self.current_dialog_id is None:
            return
        text = self.text_edit.toPlainText()
        if not text and not self.media_to_send:
            return

        media_file = None
        media_type = None
        if self.media_to_send:
            media_file = os.path.relpath(self.media_to_send, BASE_DIR)
            ext = os.path.splitext(self.media_to_send)[1].lower()
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
            "text": text,
            "date": datetime.now().isoformat(),
            "media_file": media_file,
            "media_type": media_type,
            "delivered": False
        }
        try:
            r = requests.post(f"{API_BASE}/messages/", json=payload)
            if r.status_code in (200, 201):
                self.text_edit.clear()
                self.media_to_send = None
                # обновляем диалог после отправки и скроллим вниз
                self.load_messages(self.dialog_list.currentItem(), scroll_to_bottom=True)
        except Exception as e:
            print("Ошибка отправки сообщения:", e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ChatGUI()
    gui.show()
    sys.exit(app.exec())
