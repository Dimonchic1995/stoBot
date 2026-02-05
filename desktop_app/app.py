import datetime as dt
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

import requests
from PySide6.QtCore import Qt, QDate, QTime, Signal, QObject
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QDialog,
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
    QTimeEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from config import AppConfig, load_config, save_config
from db import Database
from google_calendar_client import GoogleCalendarClient
from local_api import LocalApiServer
from telegram_client import TelegramClient


class ApiBridge(QObject):
    message_received = Signal(dict)


class ScheduleDialog(QDialog):
    def __init__(self, service_types: List[str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Запланувати час")
        self.service_box = QComboBox()
        self.service_box.addItems(service_types)
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.time_edit = QTimeEdit()
        self.time_edit.setTime(QTime.currentTime())
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(15, 240)
        self.duration_spin.setValue(60)
        form = QFormLayout()
        form.addRow("Послуга:", self.service_box)
        form.addRow("Дата:", self.date_edit)
        form.addRow("Час:", self.time_edit)
        form.addRow("Тривалість (хв):", self.duration_spin)
        buttons_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(ok_btn)
        buttons_layout.addWidget(cancel_btn)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons_layout)
        self.setLayout(layout)

    def get_data(self) -> Dict[str, str]:
        return {
            "service_type": self.service_box.currentText(),
            "date": self.date_edit.date().toPython(),
            "time": self.time_edit.time().toPython(),
            "duration": self.duration_spin.value(),
        }


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("StoDesktop")
        self.base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        self.data_dir = self.base_dir / "data"
        self.logs_dir = self.base_dir / "logs"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.logs_dir / "app.log"
        self._setup_logging()
        self.logger = logging.getLogger("stod")
        self.config_path = self.data_dir / "config.json"
        self.config = load_config(self.config_path)
        self.db = Database(self.data_dir / "app.db")
        self.api_bridge = ApiBridge()
        self.api_bridge.message_received.connect(self.on_incoming_message)
        self.local_api: Optional[LocalApiServer] = None
        self.telegram_client: Optional[TelegramClient] = None
        self.calendar_client: Optional[GoogleCalendarClient] = None
        self.chat_tabs: Dict[str, QWidget] = {}

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.chats_tab = QWidget()
        self.calendar_tab = QWidget()
        self.settings_tab = QWidget()
        self.logs_tab = QWidget()

        self.tabs.addTab(self.chats_tab, "Чати")
        self.tabs.addTab(self.calendar_tab, "Календар")
        self.tabs.addTab(self.settings_tab, "Налаштування")
        self.tabs.addTab(self.logs_tab, "Логи/Помилки")

        self._build_chats_tab()
        self._build_calendar_tab()
        self._build_settings_tab()
        self._build_logs_tab()

        self.reload_chats()
        self.apply_config(self.config, initial=True)

    def _setup_logging(self) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            handlers=[
                logging.FileHandler(self.log_file, encoding="utf-8"),
                logging.StreamHandler(sys.stdout),
            ],
        )

    def _build_chats_tab(self) -> None:
        layout = QHBoxLayout()
        self.chat_list = QListWidget()
        self.chat_list.itemClicked.connect(self.open_chat_from_list)
        self.chat_tabs_widget = QTabWidget()
        layout.addWidget(self.chat_list, 1)
        layout.addWidget(self.chat_tabs_widget, 3)
        self.chats_tab.setLayout(layout)

    def _build_calendar_tab(self) -> None:
        layout = QVBoxLayout()
        controls = QHBoxLayout()
        self.calendar_combo = QComboBox()
        self.period_combo = QComboBox()
        self.period_combo.addItems(["Today", "Week"])
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_calendar)
        controls.addWidget(QLabel("Calendar:"))
        controls.addWidget(self.calendar_combo)
        controls.addWidget(QLabel("Period:"))
        controls.addWidget(self.period_combo)
        controls.addWidget(refresh_btn)
        self.events_table = QTableWidget(0, 3)
        self.events_table.setHorizontalHeaderLabels(["Start", "End", "Summary"])
        layout.addLayout(controls)
        layout.addWidget(self.events_table)
        self.calendar_tab.setLayout(layout)

    def _build_settings_tab(self) -> None:
        layout = QVBoxLayout()
        form = QFormLayout()
        self.bot_token_input = QLineEdit()
        self.shared_secret_input = QLineEdit()
        self.port_input = QLineEdit()
        self.google_creds_input = QLineEdit()
        creds_btn = QPushButton("Обрати файл")
        creds_btn.clicked.connect(self.select_creds_file)
        creds_layout = QHBoxLayout()
        creds_layout.addWidget(self.google_creds_input)
        creds_layout.addWidget(creds_btn)

        form.addRow("Telegram Bot Token:", self.bot_token_input)
        form.addRow("Shared Secret:", self.shared_secret_input)
        form.addRow("Local API Port:", self.port_input)
        form.addRow("Google creds path:", creds_layout)

        self.mapping_table = QTableWidget(0, 2)
        self.mapping_table.setHorizontalHeaderLabels(["Service Type", "Calendar ID"])
        add_row_btn = QPushButton("Add row")
        add_row_btn.clicked.connect(self.add_mapping_row)

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_settings)
        self.test_telegram_btn = QPushButton("Test Telegram")
        self.test_telegram_btn.clicked.connect(self.test_telegram)
        self.test_google_btn = QPushButton("Test Google Calendar")
        self.test_google_btn.clicked.connect(self.test_google)
        self.test_local_btn = QPushButton("Test Local API")
        self.test_local_btn.clicked.connect(self.test_local_api)

        self.telegram_status = QLabel("-")
        self.google_status = QLabel("-")
        self.local_status = QLabel("-")

        test_layout = QHBoxLayout()
        test_layout.addWidget(self.save_btn)
        test_layout.addWidget(self.test_telegram_btn)
        test_layout.addWidget(self.test_google_btn)
        test_layout.addWidget(self.test_local_btn)

        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Telegram:"))
        status_layout.addWidget(self.telegram_status)
        status_layout.addWidget(QLabel("Google:"))
        status_layout.addWidget(self.google_status)
        status_layout.addWidget(QLabel("Local API:"))
        status_layout.addWidget(self.local_status)

        layout.addLayout(form)
        layout.addWidget(QLabel("Mapping service_type -> calendar_id"))
        layout.addWidget(self.mapping_table)
        layout.addWidget(add_row_btn)
        layout.addLayout(test_layout)
        layout.addLayout(status_layout)
        self.settings_tab.setLayout(layout)

    def _build_logs_tab(self) -> None:
        layout = QVBoxLayout()
        self.logs_view = QTextEdit()
        self.logs_view.setReadOnly(True)
        refresh_btn = QPushButton("Refresh logs")
        refresh_btn.clicked.connect(self.refresh_logs)
        layout.addWidget(refresh_btn)
        layout.addWidget(self.logs_view)
        self.logs_tab.setLayout(layout)

    def select_creds_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select creds.json", str(self.base_dir))
        if path:
            self.google_creds_input.setText(path)

    def add_mapping_row(self) -> None:
        row = self.mapping_table.rowCount()
        self.mapping_table.insertRow(row)

    def save_settings(self) -> None:
        config = AppConfig(
            bot_token=self.bot_token_input.text().strip(),
            shared_secret=self.shared_secret_input.text().strip(),
            local_api_port=int(self.port_input.text().strip() or 0),
            google_creds_path=self.google_creds_input.text().strip(),
            service_calendar_map=self._collect_mapping(),
        )
        save_config(self.config_path, config)
        self.apply_config(config, initial=False)
        QMessageBox.information(self, "Saved", "Configuration saved")

    def _collect_mapping(self) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for row in range(self.mapping_table.rowCount()):
            service_item = self.mapping_table.item(row, 0)
            calendar_item = self.mapping_table.item(row, 1)
            if not service_item or not calendar_item:
                continue
            service = service_item.text().strip()
            calendar_id = calendar_item.text().strip()
            if service and calendar_id:
                mapping[service] = calendar_id
        return mapping

    def apply_config(self, config: AppConfig, initial: bool) -> None:
        self.config = config
        self.bot_token_input.setText(config.bot_token)
        self.shared_secret_input.setText(config.shared_secret)
        self.port_input.setText(str(config.local_api_port))
        self.google_creds_input.setText(config.google_creds_path)
        self.mapping_table.setRowCount(0)
        for service, calendar_id in config.service_calendar_map.items():
            row = self.mapping_table.rowCount()
            self.mapping_table.insertRow(row)
            self.mapping_table.setItem(row, 0, QTableWidgetItem(service))
            self.mapping_table.setItem(row, 1, QTableWidgetItem(calendar_id))
        valid, missing = config.validate()
        if not valid:
            missing_str = ", ".join(missing)
            self.logger.error("CONFIG_MISSING: %s", missing_str)
            QMessageBox.warning(self, "Config missing", f"CONFIG_MISSING: {missing_str}")
            self.tabs.setCurrentWidget(self.settings_tab)
        self._toggle_actions(valid)
        self._setup_clients(valid)
        self._setup_local_api(initial)
        self.refresh_calendar_combo()

    def _toggle_actions(self, enabled: bool) -> None:
        for widget in self.chat_tabs.values():
            send_btn = widget.findChild(QPushButton, "send_button")
            schedule_btn = widget.findChild(QPushButton, "schedule_button")
            if send_btn:
                send_btn.setEnabled(enabled)
            if schedule_btn:
                schedule_btn.setEnabled(enabled)

    def _setup_clients(self, enabled: bool) -> None:
        self.telegram_client = TelegramClient(self.config.bot_token, self.logger) if enabled else None
        if enabled:
            try:
                self.calendar_client = GoogleCalendarClient(self.config.google_creds_path)
            except Exception as exc:
                self.logger.error("Google Calendar init failed: %s", exc)
                self.calendar_client = None
        else:
            self.calendar_client = None

    def _setup_local_api(self, initial: bool) -> None:
        if self.local_api:
            if self.local_api.port == self.config.local_api_port and not initial:
                return
            self.local_api.stop()
        self.local_api = LocalApiServer(
            host="127.0.0.1",
            port=self.config.local_api_port or 8765,
            secret=self.config.shared_secret,
            logger=self.logger,
        )
        self.local_api.start(self.api_bridge.message_received.emit)

    def refresh_logs(self) -> None:
        if self.log_file.exists():
            self.logs_view.setPlainText(self.log_file.read_text(encoding="utf-8"))

    def reload_chats(self) -> None:
        self.chat_list.clear()
        for chat in self.db.list_chats():
            item = QListWidgetItem(f"{chat['display_name']} ({chat['unread_count']})")
            item.setData(Qt.UserRole, chat["chat_id"])
            self.chat_list.addItem(item)

    def open_chat_from_list(self, item: QListWidgetItem) -> None:
        chat_id = item.data(Qt.UserRole)
        display_name = item.text().split(" (")[0]
        self.open_chat_tab(chat_id, display_name)

    def open_chat_tab(self, chat_id: str, display_name: str) -> None:
        if chat_id in self.chat_tabs:
            index = self.chat_tabs_widget.indexOf(self.chat_tabs[chat_id])
            self.chat_tabs_widget.setCurrentIndex(index)
            return
        tab = QWidget()
        layout = QVBoxLayout()
        messages_view = QTextEdit()
        messages_view.setReadOnly(True)
        layout.addWidget(messages_view)

        input_layout = QHBoxLayout()
        input_field = QLineEdit()
        send_btn = QPushButton("Надіслати")
        send_btn.setObjectName("send_button")
        send_btn.clicked.connect(lambda: self.send_message(chat_id, input_field, messages_view))
        schedule_btn = QPushButton("Запланувати час")
        schedule_btn.setObjectName("schedule_button")
        schedule_btn.clicked.connect(lambda: self.schedule_time(chat_id, display_name))
        input_layout.addWidget(input_field)
        input_layout.addWidget(send_btn)
        input_layout.addWidget(schedule_btn)
        layout.addLayout(input_layout)
        tab.setLayout(layout)
        self.chat_tabs_widget.addTab(tab, display_name)
        self.chat_tabs[chat_id] = tab
        self._load_messages(chat_id, messages_view)
        valid, _ = self.config.validate()
        send_btn.setEnabled(valid)
        schedule_btn.setEnabled(valid)
        self.db.update_unread(chat_id, 0)
        self.reload_chats()

    def _load_messages(self, chat_id: str, view: QTextEdit) -> None:
        messages = self.db.list_messages(chat_id)
        lines = []
        for msg in messages:
            lines.append(f"[{msg['ts']}] {msg['direction']}: {msg['text']}")
        view.setPlainText("\n".join(lines))
        view.moveCursor(view.textCursor().End)

    def append_message(self, chat_id: str, direction: str, text: str, ts: str) -> None:
        tab = self.chat_tabs.get(chat_id)
        if tab:
            view = tab.findChild(QTextEdit)
            if view:
                view.append(f"[{ts}] {direction}: {text}")

    def on_incoming_message(self, payload: dict) -> None:
        chat_id = str(payload.get("chat_id"))
        display_name = payload.get("user_name", "") or chat_id
        text = payload.get("text", "")
        ts = payload.get("ts") or dt.datetime.utcnow().isoformat()
        meta_json = json.dumps(payload, ensure_ascii=False)
        self.db.upsert_chat(chat_id, display_name, ts)
        self.db.add_message(chat_id, "in", text, ts, status="sent", meta_json=meta_json)
        if chat_id not in self.chat_tabs:
            self.db.increment_unread(chat_id)
        self.append_message(chat_id, "in", text, ts)
        self.reload_chats()

    def send_message(self, chat_id: str, input_field: QLineEdit, view: QTextEdit) -> None:
        text = input_field.text().strip()
        if not text:
            return
        if not self.telegram_client:
            QMessageBox.warning(self, "Config", "Config invalid")
            return
        ts = dt.datetime.utcnow().isoformat()
        success, error = self.telegram_client.send_message(chat_id, text)
        status = "sent" if success else "failed"
        if not success:
            self.logger.error("Send message failed: %s", error)
            QMessageBox.warning(self, "Send failed", error)
        self.db.add_message(chat_id, "out", text, ts, status=status, meta_json=None)
        view.append(f"[{ts}] out: {text}")
        input_field.clear()

    def schedule_time(self, chat_id: str, display_name: str) -> None:
        if not self.calendar_client or not self.telegram_client:
            QMessageBox.warning(self, "Config", "Config invalid")
            return
        dialog = ScheduleDialog(list(self.config.service_calendar_map.keys()), self)
        if dialog.exec() != QDialog.Accepted:
            return
        data = dialog.get_data()
        service_type = data["service_type"]
        calendar_id = self.config.service_calendar_map.get(service_type)
        if not calendar_id:
            QMessageBox.warning(self, "Calendar", "No calendar mapping")
            return
        start_dt = dt.datetime.combine(data["date"], data["time"])
        end_dt = start_dt + dt.timedelta(minutes=int(data["duration"]))
        try:
            events = self.calendar_client.list_events(calendar_id, start_dt, end_dt)
        except Exception as exc:
            self.logger.error("Calendar list failed: %s", exc)
            QMessageBox.warning(self, "Calendar", str(exc))
            return
        if events:
            QMessageBox.warning(self, "Calendar", "Time slot busy")
            return
        try:
            event_id, event = self.calendar_client.create_event(
                calendar_id,
                summary=f"{service_type} - {display_name}",
                description=f"Chat {chat_id}",
                start_dt=start_dt,
                end_dt=end_dt,
            )
        except Exception as exc:
            self.logger.error("Calendar create failed: %s", exc)
            QMessageBox.warning(self, "Calendar", str(exc))
            return
        self.db.add_calendar_event(
            chat_id,
            calendar_id,
            event_id,
            start_dt.isoformat(),
            end_dt.isoformat(),
            dt.datetime.utcnow().isoformat(),
        )
        confirmation = (
            f"Запис підтверджено: {start_dt.strftime('%Y-%m-%d %H:%M')}, {data['duration']} хв"
        )
        success, error = self.telegram_client.send_message(chat_id, confirmation)
        status = "sent" if success else "failed"
        self.db.add_message(chat_id, "out", confirmation, dt.datetime.utcnow().isoformat(), status=status)
        if not success:
            self.logger.error("Confirmation send failed: %s", error)
            QMessageBox.warning(self, "Telegram", error)

    def refresh_calendar_combo(self) -> None:
        self.calendar_combo.clear()
        for _, calendar_id in self.config.service_calendar_map.items():
            self.calendar_combo.addItem(calendar_id)

    def refresh_calendar(self) -> None:
        if not self.calendar_client:
            QMessageBox.warning(self, "Calendar", "Config invalid")
            return
        calendar_id = self.calendar_combo.currentText()
        if not calendar_id:
            return
        now = dt.datetime.utcnow()
        if self.period_combo.currentText() == "Today":
            start = dt.datetime(now.year, now.month, now.day)
            end = start + dt.timedelta(days=1)
        else:
            start = dt.datetime(now.year, now.month, now.day)
            end = start + dt.timedelta(days=7)
        try:
            events = self.calendar_client.list_events(calendar_id, start, end)
        except Exception as exc:
            self.logger.error("Calendar list failed: %s", exc)
            QMessageBox.warning(self, "Calendar", str(exc))
            return
        self.events_table.setRowCount(0)
        for event in events:
            row = self.events_table.rowCount()
            self.events_table.insertRow(row)
            start_val = event.get("start", {}).get("dateTime", "")
            end_val = event.get("end", {}).get("dateTime", "")
            summary = event.get("summary", "")
            self.events_table.setItem(row, 0, QTableWidgetItem(start_val))
            self.events_table.setItem(row, 1, QTableWidgetItem(end_val))
            self.events_table.setItem(row, 2, QTableWidgetItem(summary))

    def test_telegram(self) -> None:
        client = TelegramClient(self.bot_token_input.text().strip(), self.logger)
        ok, msg = client.test()
        self.telegram_status.setText("OK" if ok else f"FAIL: {msg}")

    def test_google(self) -> None:
        try:
            client = GoogleCalendarClient(self.google_creds_input.text().strip())
            calendars = client.service.calendarList().list(maxResults=1).execute()
            if calendars.get("items"):
                self.google_status.setText("OK")
            else:
                self.google_status.setText("FAIL: no calendars")
        except Exception as exc:
            self.google_status.setText(f"FAIL: {exc}")

    def test_local_api(self) -> None:
        port = int(self.port_input.text().strip() or 8765)
        body = {
            "chat_id": "test",
            "user_name": "Test",
            "text": "Ping",
            "ts": dt.datetime.utcnow().isoformat(),
            "message_id": "test",
        }
        raw = json.dumps(body).encode("utf-8")
        secret = self.shared_secret_input.text().strip().encode("utf-8")
        signature = hmac_sha256(secret, raw)
        try:
            response = requests.post(
                f"http://127.0.0.1:{port}/api/telegram/incoming",
                data=raw,
                headers={"X-Signature": signature, "Content-Type": "application/json"},
                timeout=5,
            )
        except requests.RequestException as exc:
            self.local_status.setText(f"FAIL: {exc}")
            return
        if response.status_code == 200:
            self.local_status.setText("OK")
        else:
            self.local_status.setText(f"FAIL: {response.text}")


def hmac_sha256(secret: bytes, body: bytes) -> str:
    import hmac

    return hmac.new(secret, body, "sha256").hexdigest()


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
