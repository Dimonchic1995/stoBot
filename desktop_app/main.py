import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from api_server import LocalAPIServer
from calendar_client import CalendarClient
from config_manager import AppConfig, ConfigManager
from database import Database
from telegram_client import TelegramClient

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "app.db"
CONFIG_PATH = DATA_DIR / "config.json"
LOG_PATH = LOG_DIR / "app.log"


class LogHandler(logging.Handler):
    def __init__(self, widget: QTextEdit):
        super().__init__()
        self.widget = widget

    def emit(self, record):
        msg = self.format(record)
        self.widget.append(msg)


class IncomingSignal(QObject):
    incoming = Signal(dict)


@dataclass
class ChatTab:
    chat_id: str
    display_name: str
    widget: QWidget
    history: QTextEdit
    input_field: QLineEdit
    send_button: QPushButton
    schedule_button: QPushButton


class ScheduleDialog(QDialog):
    def __init__(self, calendar_ids: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Запланувати час")
        layout = QFormLayout(self)
        self.datetime_edit = QDateTimeEdit(datetime.now())
        self.datetime_edit.setCalendarPopup(True)
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(15, 240)
        self.duration_spin.setValue(30)
        self.calendar_combo = QComboBox()
        self.calendar_combo.addItems(calendar_ids)
        layout.addRow("Дата/час", self.datetime_edit)
        layout.addRow("Тривалість (хв)", self.duration_spin)
        layout.addRow("Календар", self.calendar_combo)
        button_row = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(ok_btn)
        button_row.addWidget(cancel_btn)
        layout.addRow(button_row)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("StoDesktop")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            handlers=[
                logging.FileHandler(LOG_PATH, encoding="utf-8"),
            ],
        )
        self.db = Database(DB_PATH)
        self.config_manager = ConfigManager(CONFIG_PATH)
        self.config = self.config_manager.load()
        self.api_server: LocalAPIServer | None = None
        self.incoming_signal = IncomingSignal()
        self.incoming_signal.incoming.connect(self.handle_incoming)
        self.chat_tabs: dict[str, ChatTab] = {}
        self.config_valid = False

        self._build_ui()
        self._load_chats()
        self._validate_config()
        self._start_local_api()

    def _build_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.chat_tab = QWidget()
        self.calendar_tab = QWidget()
        self.settings_tab = QWidget()
        self.logs_tab = QWidget()

        self.tabs.addTab(self.chat_tab, "Чати")
        self.tabs.addTab(self.calendar_tab, "Календар")
        self.tabs.addTab(self.settings_tab, "Налаштування")
        self.tabs.addTab(self.logs_tab, "Логи/Помилки")

        self._build_chat_tab()
        self._build_calendar_tab()
        self._build_settings_tab()
        self._build_logs_tab()

        self.setCentralWidget(container)

    def _build_chat_tab(self):
        layout = QHBoxLayout(self.chat_tab)
        self.chat_list = QListWidget()
        self.chat_list.itemClicked.connect(self._open_chat)
        layout.addWidget(self.chat_list, 1)
        self.chat_content_tabs = QTabWidget()
        layout.addWidget(self.chat_content_tabs, 3)

    def _build_calendar_tab(self):
        layout = QVBoxLayout(self.calendar_tab)
        filter_row = QHBoxLayout()
        self.calendar_period = QComboBox()
        self.calendar_period.addItems(["today", "week"])
        self.calendar_select = QComboBox()
        self.calendar_refresh = QPushButton("Refresh")
        self.calendar_refresh.clicked.connect(self._refresh_calendar)
        filter_row.addWidget(QLabel("Період"))
        filter_row.addWidget(self.calendar_period)
        filter_row.addWidget(QLabel("Календар"))
        filter_row.addWidget(self.calendar_select)
        filter_row.addWidget(self.calendar_refresh)
        layout.addLayout(filter_row)
        self.calendar_events_view = QTextEdit()
        self.calendar_events_view.setReadOnly(True)
        layout.addWidget(self.calendar_events_view)

    def _build_settings_tab(self):
        layout = QVBoxLayout(self.settings_tab)
        form = QFormLayout()
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.Password)
        self.secret_input = QLineEdit()
        self.secret_input.setEchoMode(QLineEdit.Password)
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.creds_input = QLineEdit()
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_creds)
        creds_layout = QHBoxLayout()
        creds_layout.addWidget(self.creds_input)
        creds_layout.addWidget(browse_btn)

        self.mapping_table = QTableWidget(0, 2)
        self.mapping_table.setHorizontalHeaderLabels(["service_type", "calendar_id"])

        form.addRow("Telegram Bot Token", self.token_input)
        form.addRow("Shared Secret", self.secret_input)
        form.addRow("Local API Port", self.port_input)
        form.addRow("Google creds path", creds_layout)
        layout.addLayout(form)
        layout.addWidget(QLabel("Mapping service_type -> calendar_id"))
        layout.addWidget(self.mapping_table)
        mapping_btn_row = QHBoxLayout()
        add_mapping_btn = QPushButton("Add mapping")
        add_mapping_btn.clicked.connect(self._add_mapping_row)
        mapping_btn_row.addWidget(add_mapping_btn)
        layout.addLayout(mapping_btn_row)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save_settings)
        self.test_telegram_btn = QPushButton("Test Telegram")
        self.test_telegram_btn.clicked.connect(self._test_telegram)
        self.test_google_btn = QPushButton("Test Google Calendar")
        self.test_google_btn.clicked.connect(self._test_google)
        self.test_local_btn = QPushButton("Test Local API")
        self.test_local_btn.clicked.connect(self._test_local_api)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.test_telegram_btn)
        btn_row.addWidget(self.test_google_btn)
        btn_row.addWidget(self.test_local_btn)
        layout.addLayout(btn_row)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        self._load_settings_into_form()

    def _build_logs_tab(self):
        layout = QVBoxLayout(self.logs_tab)
        self.logs_view = QTextEdit()
        self.logs_view.setReadOnly(True)
        layout.addWidget(self.logs_view)
        handler = LogHandler(self.logs_view)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logging.getLogger().addHandler(handler)

        if LOG_PATH.exists():
            self.logs_view.setPlainText(LOG_PATH.read_text(encoding="utf-8"))

    def _load_settings_into_form(self):
        self.token_input.setText(self.config.telegram_bot_token)
        self.secret_input.setText(self.config.shared_secret)
        self.port_input.setValue(self.config.local_api_port)
        self.creds_input.setText(self.config.google_creds_path)
        self.mapping_table.setRowCount(0)
        for service_type, calendar_id in self.config.calendar_mapping.items():
            row = self.mapping_table.rowCount()
            self.mapping_table.insertRow(row)
            self.mapping_table.setItem(row, 0, QTableWidgetItem(service_type))
            self.mapping_table.setItem(row, 1, QTableWidgetItem(calendar_id))
        self._refresh_calendar_select()

    def _refresh_calendar_select(self):
        self.calendar_select.clear()
        ids = list(self.config.calendar_mapping.values())
        if not ids:
            ids = ["primary"]
        self.calendar_select.addItems(ids)

    def _save_settings(self):
        mapping = {}
        for row in range(self.mapping_table.rowCount()):
            key_item = self.mapping_table.item(row, 0)
            value_item = self.mapping_table.item(row, 1)
            if key_item and value_item and key_item.text() and value_item.text():
                mapping[key_item.text()] = value_item.text()
        self.config = AppConfig(
            telegram_bot_token=self.token_input.text().strip(),
            shared_secret=self.secret_input.text().strip(),
            local_api_port=self.port_input.value(),
            google_creds_path=self.creds_input.text().strip(),
            calendar_mapping=mapping,
        )
        self.config_manager.save(self.config)
        self._validate_config()
        self._restart_local_api()
        self._refresh_calendar_select()
        self.status_label.setText("Saved")

    def _browse_creds(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select creds.json", str(BASE_DIR))
        if path:
            self.creds_input.setText(path)

    def _add_mapping_row(self):
        row = self.mapping_table.rowCount()
        self.mapping_table.insertRow(row)
        self.mapping_table.setItem(row, 0, QTableWidgetItem(""))
        self.mapping_table.setItem(row, 1, QTableWidgetItem(""))

    def _validate_config(self):
        missing = self.config.missing_fields()
        if missing:
            message = f"CONFIG_MISSING: {', '.join(missing)}"
            logging.error(message)
            self.status_label.setText(message)
            QMessageBox.warning(self, "Config missing", message)
            self.tabs.setCurrentWidget(self.settings_tab)
            self.config_valid = False
            self._toggle_config_actions(False)
        else:
            self.config_valid = True
            self._toggle_config_actions(True)
            self.status_label.setText("Config OK")

    def _toggle_config_actions(self, enabled: bool):
        for tab in self.chat_tabs.values():
            tab.send_button.setEnabled(enabled)
            tab.schedule_button.setEnabled(enabled)
        self.calendar_refresh.setEnabled(enabled)
        self.calendar_select.setEnabled(enabled)

    def _load_chats(self):
        self.chat_list.clear()
        for chat in self.db.list_chats():
            label = f"{chat['display_name']} ({chat['unread_count']})"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, chat["chat_id"])
            self.chat_list.addItem(item)

    def _open_chat(self, item: QListWidgetItem):
        chat_id = item.data(Qt.UserRole)
        if chat_id in self.chat_tabs:
            self.chat_content_tabs.setCurrentWidget(self.chat_tabs[chat_id].widget)
            self.db.reset_unread(chat_id)
            self._load_chats()
            return

        widget = QWidget()
        layout = QVBoxLayout(widget)
        history = QTextEdit()
        history.setReadOnly(True)
        layout.addWidget(history)
        input_row = QHBoxLayout()
        input_field = QLineEdit()
        send_button = QPushButton("Надіслати")
        send_button.clicked.connect(lambda: self._send_message(chat_id))
        schedule_button = QPushButton("Запланувати час")
        schedule_button.clicked.connect(lambda: self._schedule_time(chat_id))
        input_row.addWidget(input_field)
        input_row.addWidget(send_button)
        input_row.addWidget(schedule_button)
        layout.addLayout(input_row)

        chat_tab = ChatTab(
            chat_id=chat_id,
            display_name=item.text(),
            widget=widget,
            history=history,
            input_field=input_field,
            send_button=send_button,
            schedule_button=schedule_button,
        )
        self.chat_tabs[chat_id] = chat_tab
        self.chat_content_tabs.addTab(widget, item.text())
        self.chat_content_tabs.setCurrentWidget(widget)
        self._load_history(chat_id)
        if not self.config_valid:
            chat_tab.send_button.setEnabled(False)
            chat_tab.schedule_button.setEnabled(False)
        self.db.reset_unread(chat_id)
        self._load_chats()

    def _load_history(self, chat_id: str):
        tab = self.chat_tabs[chat_id]
        tab.history.clear()
        for msg in self.db.list_messages(chat_id):
            ts = msg["ts"]
            direction = msg["direction"]
            text = msg["text"]
            tab.history.append(f"[{ts}] {direction}: {text}")

    def _send_message(self, chat_id: str):
        tab = self.chat_tabs[chat_id]
        text = tab.input_field.text().strip()
        if not text:
            return
        client = TelegramClient(self.config.telegram_bot_token)
        ok, info = client.send_message(chat_id, text)
        ts = datetime.utcnow().isoformat()
        status = "sent" if ok else "failed"
        self.db.add_message(chat_id, "out", text, ts, status)
        if not ok:
            logging.error("Send failed: %s", info)
            QMessageBox.warning(self, "Send failed", info)
        tab.input_field.clear()
        self._load_history(chat_id)

    def _schedule_time(self, chat_id: str):
        calendar_ids = list(self.config.calendar_mapping.values()) or ["primary"]
        dialog = ScheduleDialog(calendar_ids, self)
        if dialog.exec() != QDialog.Accepted:
            return
        start = dialog.datetime_edit.dateTime().toPython()
        duration = dialog.duration_spin.value()
        end = start + timedelta(minutes=duration)
        calendar_id = dialog.calendar_combo.currentText()
        try:
            client = CalendarClient(self.config.google_creds_path)
            if client.check_conflict(calendar_id, start, end):
                QMessageBox.warning(self, "Conflict", "Slot already busy")
                return
            event_id = client.create_event(
                calendar_id,
                summary=f"Chat {chat_id}",
                start=start,
                end=end,
            )
            self.db.add_calendar_event(
                chat_id,
                calendar_id,
                event_id,
                start.isoformat(),
                end.isoformat(),
            )
            client = TelegramClient(self.config.telegram_bot_token)
            message = f"Запис підтверджено: {start.strftime('%Y-%m-%d %H:%M')}, {duration} хв"
            ok, info = client.send_message(chat_id, message)
            if not ok:
                logging.error("Failed to send confirmation: %s", info)
                QMessageBox.warning(self, "Telegram", info)
        except Exception as exc:
            logging.error("Schedule error: %s", exc)
            QMessageBox.warning(self, "Schedule", str(exc))

    def _refresh_calendar(self):
        period = self.calendar_period.currentText()
        calendar_id = self.calendar_select.currentText()
        try:
            client = CalendarClient(self.config.google_creds_path)
            start, end = client.build_range(period)
            events = client.list_events(calendar_id, start, end)
            lines = []
            for event in events:
                start_time = event.get("start", {}).get("dateTime", "")
                summary = event.get("summary", "")
                lines.append(f"{start_time} - {summary}")
            self.calendar_events_view.setPlainText("\n".join(lines))
        except Exception as exc:
            logging.error("Calendar refresh error: %s", exc)
            QMessageBox.warning(self, "Calendar", str(exc))

    def _test_telegram(self):
        try:
            import requests

            token = self.token_input.text().strip()
            response = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
            if response.status_code == 200:
                self.status_label.setText("Telegram OK")
            else:
                self.status_label.setText(f"Telegram FAIL: {response.text}")
        except Exception as exc:
            self.status_label.setText(f"Telegram FAIL: {exc}")

    def _test_google(self):
        try:
            client = CalendarClient(self.creds_input.text().strip())
            start, end = client.build_range("today")
            calendar_id = self.calendar_select.currentText()
            client.list_events(calendar_id, start, end)
            self.status_label.setText("Google Calendar OK")
        except Exception as exc:
            self.status_label.setText(f"Google Calendar FAIL: {exc}")

    def _test_local_api(self):
        import requests
        import hmac

        body = json.dumps({"chat_id": "1", "user_name": "test", "text": "ping", "ts": "", "message_id": ""})
        signature = hmac.new(
            self.secret_input.text().strip().encode("utf-8"),
            body.encode("utf-8"),
            "sha256",
        ).hexdigest()
        try:
            response = requests.post(
                f"http://127.0.0.1:{self.port_input.value()}/api/telegram/incoming",
                data=body,
                headers={"X-Signature": signature, "Content-Type": "application/json"},
                timeout=5,
            )
            if response.status_code == 200:
                self.status_label.setText("Local API OK")
            else:
                self.status_label.setText(f"Local API FAIL: {response.status_code}")
        except Exception as exc:
            self.status_label.setText(f"Local API FAIL: {exc}")

    def _start_local_api(self):
        if not self.config.shared_secret:
            return
        self.api_server = LocalAPIServer(
            "127.0.0.1", self.config.local_api_port, self.config.shared_secret, self._emit_incoming
        )
        try:
            self.api_server.start()
        except OSError as exc:
            logging.error("Local API start error: %s", exc)

    def _restart_local_api(self):
        if self.api_server:
            self.api_server.stop()
        self._start_local_api()

    def _emit_incoming(self, payload: dict):
        self.incoming_signal.incoming.emit(payload)

    def handle_incoming(self, payload: dict):
        chat_id = str(payload.get("chat_id"))
        display_name = payload.get("user_name") or chat_id
        text = payload.get("text") or ""
        ts = payload.get("ts") or datetime.utcnow().isoformat()
        self.db.upsert_chat(chat_id, display_name, ts)
        self.db.add_message(chat_id, "in", text, ts, "sent")
        self.db.increment_unread(chat_id)
        self._load_chats()
        if chat_id in self.chat_tabs:
            self._load_history(chat_id)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
