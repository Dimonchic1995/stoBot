import json
import logging
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Qt
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
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app_config import AppConfig, load_config, save_config, validate_config
from calendar_client import create_event, has_conflict, list_events
from database import Database
from local_api import LocalApiServer
from logging_setup import setup_logging
from telegram_client import send_message

APP_ROOT = Path(__file__).resolve().parent
DATA_DIR = APP_ROOT / "data"
LOG_DIR = APP_ROOT / "logs"
CONFIG_PATH = DATA_DIR / "config.json"
DB_PATH = DATA_DIR / "app.db"
LOG_PATH = LOG_DIR / "app.log"


class ScheduleDialog(QDialog):
    def __init__(self, calendar_ids: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Запланувати час")
        layout = QFormLayout(self)

        self.calendar_combo = QComboBox()
        self.calendar_combo.addItems(calendar_ids)

        self.datetime_edit = QDateTimeEdit(datetime.now())
        self.datetime_edit.setCalendarPopup(True)
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(15, 240)
        self.duration_spin.setSingleStep(15)
        self.duration_spin.setValue(30)

        layout.addRow("Календар:", self.calendar_combo)
        layout.addRow("Дата і час:", self.datetime_edit)
        layout.addRow("Тривалість (хв):", self.duration_spin)

        buttons = QHBoxLayout()
        self.confirm_btn = QPushButton("Створити")
        self.cancel_btn = QPushButton("Скасувати")
        buttons.addWidget(self.confirm_btn)
        buttons.addWidget(self.cancel_btn)
        layout.addRow(buttons)

        self.confirm_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

    def values(self) -> tuple[str, datetime, int]:
        return (
            self.calendar_combo.currentText(),
            self.datetime_edit.dateTime().toPython(),
            self.duration_spin.value(),
        )


class ChatWidget(QWidget):
    def __init__(self, chat_id: str, db: Database, on_send, on_schedule):
        super().__init__()
        self.chat_id = chat_id
        self.db = db
        self.on_send = on_send
        self.on_schedule = on_schedule

        layout = QVBoxLayout(self)
        self.history = QTextEdit()
        self.history.setReadOnly(True)
        self.input = QLineEdit()
        self.send_btn = QPushButton("Надіслати")
        self.schedule_btn = QPushButton("Запланувати час")

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.input)
        btn_row.addWidget(self.send_btn)
        btn_row.addWidget(self.schedule_btn)

        layout.addWidget(self.history)
        layout.addLayout(btn_row)

        self.send_btn.clicked.connect(self._handle_send)
        self.schedule_btn.clicked.connect(self._handle_schedule)

    def load_history(self) -> None:
        self.history.clear()
        for row in self.db.get_messages(self.chat_id):
            self._append_message(row["direction"], row["text"], row["ts"], row["status"])

    def _append_message(self, direction: str, text: str, ts: str, status: str) -> None:
        line = f"[{ts}] {direction.upper()}: {text} ({status})"
        self.history.append(line)

    def append_outgoing(self, text: str, ts: str, status: str) -> None:
        self._append_message("out", text, ts, status)

    def append_incoming(self, text: str, ts: str) -> None:
        self._append_message("in", text, ts, "sent")

    def _handle_send(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.on_send(self.chat_id, text)
        self.input.clear()

    def _handle_schedule(self) -> None:
        self.on_schedule(self.chat_id)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sto Desktop")

        setup_logging(LOG_PATH)
        self.db = Database(DB_PATH)
        self.config = load_config(CONFIG_PATH)
        self.config_errors: list[str] = []

        self.api_server = LocalApiServer()
        self.api_server.message_received.connect(self.handle_incoming)

        self.tabs = QTabWidget()
        self.chats_tab = QWidget()
        self.calendar_tab = QWidget()
        self.settings_tab = QWidget()
        self.logs_tab = QWidget()

        self.tabs.addTab(self.chats_tab, "Чати")
        self.tabs.addTab(self.calendar_tab, "Календар")
        self.tabs.addTab(self.settings_tab, "Налаштування")
        self.tabs.addTab(self.logs_tab, "Логи/Помилки")

        self.setCentralWidget(self.tabs)
        self._build_chats_tab()
        self._build_calendar_tab()
        self._build_settings_tab()
        self._build_logs_tab()

        self.load_chats()
        self.validate_on_start()
        self.start_local_api()

    def _build_chats_tab(self) -> None:
        layout = QHBoxLayout(self.chats_tab)
        splitter = QSplitter(Qt.Horizontal)
        self.chat_list = QListWidget()
        self.chat_tabs = QTabWidget()

        splitter.addWidget(self.chat_list)
        splitter.addWidget(self.chat_tabs)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)

        self.chat_list.itemClicked.connect(self.open_chat_from_list)

    def _build_calendar_tab(self) -> None:
        layout = QVBoxLayout(self.calendar_tab)
        filter_row = QHBoxLayout()
        self.calendar_filter = QComboBox()
        self.period_filter = QComboBox()
        self.period_filter.addItems(["Today", "Week"])
        self.refresh_calendar_btn = QPushButton("Оновити")
        filter_row.addWidget(QLabel("Календар:"))
        filter_row.addWidget(self.calendar_filter)
        filter_row.addWidget(QLabel("Період:"))
        filter_row.addWidget(self.period_filter)
        filter_row.addWidget(self.refresh_calendar_btn)
        layout.addLayout(filter_row)

        self.events_table = QTableWidget(0, 4)
        self.events_table.setHorizontalHeaderLabels(["Початок", "Кінець", "Назва", "Опис"])
        layout.addWidget(self.events_table)

        self.refresh_calendar_btn.clicked.connect(self.load_calendar_events)

    def _build_settings_tab(self) -> None:
        layout = QVBoxLayout(self.settings_tab)
        form = QFormLayout()

        self.bot_token_input = QLineEdit()
        self.shared_secret_input = QLineEdit()
        self.local_port_input = QLineEdit()
        self.google_creds_input = QLineEdit()
        self.google_creds_btn = QPushButton("Обрати файл")

        creds_row = QHBoxLayout()
        creds_row.addWidget(self.google_creds_input)
        creds_row.addWidget(self.google_creds_btn)

        form.addRow("Telegram Bot Token", self.bot_token_input)
        form.addRow("Shared Secret", self.shared_secret_input)
        form.addRow("Local API Port", self.local_port_input)
        form.addRow("Google creds path", creds_row)

        self.mapping_table = QTableWidget(0, 2)
        self.mapping_table.setHorizontalHeaderLabels(["Service Type", "Calendar ID"])
        form.addRow(QLabel("Mapping service_type -> calendar_id"))
        form.addRow(self.mapping_table)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.test_telegram_btn = QPushButton("Test Telegram")
        self.test_google_btn = QPushButton("Test Google Calendar")
        self.test_local_btn = QPushButton("Test Local API")
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.test_telegram_btn)
        btn_row.addWidget(self.test_google_btn)
        btn_row.addWidget(self.test_local_btn)
        layout.addLayout(btn_row)

        status_row = QHBoxLayout()
        self.telegram_status = QLabel("Telegram: N/A")
        self.google_status = QLabel("Google: N/A")
        self.local_status = QLabel("Local API: N/A")
        status_row.addWidget(self.telegram_status)
        status_row.addWidget(self.google_status)
        status_row.addWidget(self.local_status)
        layout.addLayout(status_row)

        self.google_creds_btn.clicked.connect(self.select_creds_file)
        self.save_btn.clicked.connect(self.save_settings)
        self.test_telegram_btn.clicked.connect(self.test_telegram)
        self.test_google_btn.clicked.connect(self.test_google)
        self.test_local_btn.clicked.connect(self.test_local_api)

        self.load_settings_fields()

    def _build_logs_tab(self) -> None:
        layout = QVBoxLayout(self.logs_tab)
        self.logs_view = QTextEdit()
        self.logs_view.setReadOnly(True)
        layout.addWidget(self.logs_view)

    def log_error(self, message: str) -> None:
        logging.error(message)
        self.logs_view.append(message)

    def validate_on_start(self) -> None:
        self.config_errors = validate_config(self.config)
        if self.config_errors:
            error_text = "CONFIG_MISSING: " + ", ".join(self.config_errors)
            self.log_error(error_text)
            QMessageBox.warning(self, "Config", error_text)
            self.tabs.setCurrentWidget(self.settings_tab)
        self.update_calendar_filter()

    def start_local_api(self) -> None:
        if self.config.shared_secret and self.config.local_api_port:
            try:
                self.api_server.start(self.config.local_api_port, self.config.shared_secret)
            except OSError as exc:
                self.log_error(f"LOCAL_API_START_FAILED: {exc}")
        else:
            self.log_error("LOCAL_API_DISABLED: missing shared_secret or port")

    def handle_incoming(self, payload: dict) -> None:
        chat_id = str(payload.get("chat_id", ""))
        if not chat_id:
            self.log_error("INCOMING_MESSAGE_MISSING_CHAT_ID")
            return
        display_name = payload.get("user_name", "Unknown")
        text = payload.get("text", "")
        ts = payload.get("ts") or datetime.utcnow().isoformat()

        self.db.ensure_chat(chat_id, display_name, ts)
        self.db.add_message(chat_id, "in", text, ts, "sent", payload)
        self.update_chat_list()
        self.append_message_to_tab(chat_id, text, ts)

    def load_chats(self) -> None:
        self.update_chat_list()

    def update_chat_list(self) -> None:
        self.chat_list.clear()
        for row in self.db.get_chats():
            display = f"{row['display_name']} ({row['unread_count']})"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, row["chat_id"])
            self.chat_list.addItem(item)

    def open_chat_from_list(self, item: QListWidgetItem) -> None:
        chat_id = item.data(Qt.UserRole)
        self.open_chat_tab(chat_id)
        self.db.reset_unread(chat_id)
        self.update_chat_list()

    def open_chat_tab(self, chat_id: str) -> None:
        for index in range(self.chat_tabs.count()):
            widget = self.chat_tabs.widget(index)
            if isinstance(widget, ChatWidget) and widget.chat_id == chat_id:
                self.chat_tabs.setCurrentIndex(index)
                return
        widget = ChatWidget(chat_id, self.db, self.send_chat_message, self.schedule_chat)
        widget.load_history()
        self.chat_tabs.addTab(widget, chat_id)
        self.chat_tabs.setCurrentWidget(widget)

    def append_message_to_tab(self, chat_id: str, text: str, ts: str) -> None:
        for index in range(self.chat_tabs.count()):
            widget = self.chat_tabs.widget(index)
            if isinstance(widget, ChatWidget) and widget.chat_id == chat_id:
                widget.append_incoming(text, ts)
                return

    def send_chat_message(self, chat_id: str, text: str) -> None:
        if self.config_errors:
            QMessageBox.warning(self, "Config", "Заповніть налаштування перед відправкою.")
            return
        ts = datetime.utcnow().isoformat()
        ok, error = send_message(self.config.bot_token, chat_id, text)
        status = "sent" if ok else "failed"
        if not ok:
            self.log_error(f"SEND_FAILED: {error}")
        self.db.add_message(chat_id, "out", text, ts, status, {"error": error})
        self.append_outgoing_to_tab(chat_id, text, ts, status)

    def append_outgoing_to_tab(self, chat_id: str, text: str, ts: str, status: str) -> None:
        for index in range(self.chat_tabs.count()):
            widget = self.chat_tabs.widget(index)
            if isinstance(widget, ChatWidget) and widget.chat_id == chat_id:
                widget.append_outgoing(text, ts, status)
                return

    def schedule_chat(self, chat_id: str) -> None:
        if self.config_errors:
            QMessageBox.warning(self, "Config", "Заповніть налаштування перед плануванням.")
            return
        calendar_ids = [m.get("calendar_id") for m in self.config.calendar_mappings if m.get("calendar_id")]
        if not calendar_ids:
            QMessageBox.warning(self, "Calendar", "Відсутні календарі для планування.")
            return
        dialog = ScheduleDialog(calendar_ids, self)
        if dialog.exec() != QDialog.Accepted:
            return
        calendar_id, start_dt, duration = dialog.values()
        try:
            conflict = has_conflict(self.config.google_creds_path, calendar_id, start_dt, start_dt + timedelta(minutes=duration))
        except Exception as exc:
            self.log_error(f"CALENDAR_CONFLICT_CHECK_FAILED: {exc}")
            QMessageBox.warning(self, "Calendar", "Помилка перевірки конфліктів.")
            return
        if conflict:
            QMessageBox.warning(self, "Calendar", "Обраний слот зайнятий.")
            return
        try:
            event = create_event(
                self.config.google_creds_path,
                calendar_id,
                summary=f"Запис {chat_id}",
                description="Запис з Sto Desktop",
                start=start_dt,
                duration_minutes=duration,
            )
        except Exception as exc:
            self.log_error(f"CALENDAR_CREATE_FAILED: {exc}")
            QMessageBox.warning(self, "Calendar", "Не вдалося створити подію.")
            return
        self.db.add_calendar_event(
            chat_id,
            calendar_id,
            event.get("id", ""),
            start_dt.isoformat(),
            (start_dt + timedelta(minutes=duration)).isoformat(),
            datetime.utcnow().isoformat(),
        )
        confirmation = f"Запис підтверджено: {start_dt.strftime('%Y-%m-%d %H:%M')}, {duration} хв"
        self.send_chat_message(chat_id, confirmation)

    def update_calendar_filter(self) -> None:
        self.calendar_filter.clear()
        for mapping in self.config.calendar_mappings:
            calendar_id = mapping.get("calendar_id")
            if calendar_id:
                self.calendar_filter.addItem(calendar_id)

    def load_calendar_events(self) -> None:
        if self.config_errors:
            QMessageBox.warning(self, "Config", "Заповніть налаштування перед завантаженням подій.")
            return
        calendar_id = self.calendar_filter.currentText()
        if not calendar_id:
            return
        now = datetime.utcnow()
        if self.period_filter.currentText() == "Week":
            end = now + timedelta(days=7)
        else:
            end = now + timedelta(days=1)
        try:
            events = list_events(self.config.google_creds_path, calendar_id, now, end)
        except Exception as exc:
            self.log_error(f"CALENDAR_LOAD_FAILED: {exc}")
            QMessageBox.warning(self, "Calendar", "Не вдалося завантажити події.")
            return
        self.events_table.setRowCount(0)
        for event in events:
            start = event.get("start", {}).get("dateTime", "")
            end_time = event.get("end", {}).get("dateTime", "")
            summary = event.get("summary", "")
            description = event.get("description", "")
            row = self.events_table.rowCount()
            self.events_table.insertRow(row)
            self.events_table.setItem(row, 0, QTableWidgetItem(start))
            self.events_table.setItem(row, 1, QTableWidgetItem(end_time))
            self.events_table.setItem(row, 2, QTableWidgetItem(summary))
            self.events_table.setItem(row, 3, QTableWidgetItem(description))

    def load_settings_fields(self) -> None:
        self.bot_token_input.setText(self.config.bot_token)
        self.shared_secret_input.setText(self.config.shared_secret)
        self.local_port_input.setText(str(self.config.local_api_port))
        self.google_creds_input.setText(self.config.google_creds_path)
        self.mapping_table.setRowCount(0)
        if self.config.calendar_mappings:
            for mapping in self.config.calendar_mappings:
                row = self.mapping_table.rowCount()
                self.mapping_table.insertRow(row)
                self.mapping_table.setItem(row, 0, QTableWidgetItem(mapping.get("service_type", "")))
                self.mapping_table.setItem(row, 1, QTableWidgetItem(mapping.get("calendar_id", "")))
        else:
            self.mapping_table.insertRow(0)

    def collect_mappings(self) -> list[dict]:
        mappings = []
        for row in range(self.mapping_table.rowCount()):
            service_item = self.mapping_table.item(row, 0)
            calendar_item = self.mapping_table.item(row, 1)
            service = service_item.text().strip() if service_item else ""
            calendar = calendar_item.text().strip() if calendar_item else ""
            if service or calendar:
                mappings.append({"service_type": service, "calendar_id": calendar})
        return mappings

    def select_creds_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select creds.json", str(APP_ROOT))
        if path:
            self.google_creds_input.setText(path)

    def save_settings(self) -> None:
        try:
            port = int(self.local_port_input.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Config", "Local API Port має бути числом")
            return
        self.config = AppConfig(
            bot_token=self.bot_token_input.text().strip(),
            shared_secret=self.shared_secret_input.text().strip(),
            local_api_port=port,
            google_creds_path=self.google_creds_input.text().strip(),
            calendar_mappings=self.collect_mappings(),
        )
        save_config(CONFIG_PATH, self.config)
        self.config_errors = validate_config(self.config)
        if self.config_errors:
            error_text = "CONFIG_MISSING: " + ", ".join(self.config_errors)
            self.log_error(error_text)
            QMessageBox.warning(self, "Config", error_text)
        else:
            QMessageBox.information(self, "Config", "Налаштування збережено")
        self.update_calendar_filter()
        self.start_local_api()

    def test_telegram(self) -> None:
        import requests

        if not self.config.bot_token:
            self.telegram_status.setText("Telegram: FAIL (missing token)")
            return
        try:
            response = requests.get(
                f"https://api.telegram.org/bot{self.config.bot_token}/getMe", timeout=5
            )
        except requests.RequestException as exc:
            self.telegram_status.setText(f"Telegram: FAIL ({exc})")
            return
        if response.status_code == 200 and response.json().get("ok"):
            self.telegram_status.setText("Telegram: OK")
        else:
            self.telegram_status.setText(f"Telegram: FAIL ({response.status_code})")

    def test_google(self) -> None:
        try:
            calendar_id = self.calendar_filter.currentText()
            if not calendar_id:
                raise ValueError("Calendar ID missing")
            list_events(
                self.config.google_creds_path,
                calendar_id,
                datetime.utcnow(),
                datetime.utcnow() + timedelta(minutes=1),
            )
        except Exception as exc:
            self.google_status.setText(f"Google: FAIL ({exc})")
            return
        self.google_status.setText("Google: OK")

    def test_local_api(self) -> None:
        import hmac
        import requests

        payload = {
            "chat_id": "test",
            "user_name": "Test",
            "text": "Ping",
            "ts": datetime.utcnow().isoformat(),
            "message_id": "0",
        }
        body = json.dumps(payload).encode("utf-8")
        signature = hmac.new(
            self.config.shared_secret.encode("utf-8"), body, "sha256"
        ).hexdigest()
        try:
            response = requests.post(
                f"http://127.0.0.1:{self.config.local_api_port}/api/telegram/incoming",
                data=body,
                headers={"X-Signature": signature},
                timeout=5,
            )
        except requests.RequestException as exc:
            self.local_status.setText(f"Local API: FAIL ({exc})")
            return
        if response.status_code == 200:
            self.local_status.setText("Local API: OK")
        else:
            self.local_status.setText(f"Local API: FAIL ({response.status_code})")


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
