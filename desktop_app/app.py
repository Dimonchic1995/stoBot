import json
import logging
import os
import sys
from datetime import datetime, timedelta

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateTimeEdit,
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
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from calendar_api import create_event, has_conflict, list_events, test_access
from config_store import AppConfig
from local_api import LocalAPIServer
from storage import Database
from telegram_api import send_message, test_token


class LogEmitter(QObject):
    message = Signal(str)


class QtLogHandler(logging.Handler):
    def __init__(self, emitter: LogEmitter):
        super().__init__()
        self.emitter = emitter

    def emit(self, record):
        msg = self.format(record)
        self.emitter.message.emit(msg)


def get_app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class ScheduleDialog(QDialog):
    def __init__(self, calendar_ids):
        super().__init__()
        self.setWindowTitle("Запланувати час")
        layout = QFormLayout(self)
        self.date_time = QDateTimeEdit(datetime.now())
        self.date_time.setCalendarPopup(True)
        self.duration = QSpinBox()
        self.duration.setRange(15, 480)
        self.duration.setSingleStep(15)
        self.duration.setValue(60)
        self.calendar_combo = QComboBox()
        for item in calendar_ids:
            self.calendar_combo.addItem(item)
        layout.addRow("Дата/час", self.date_time)
        layout.addRow("Тривалість (хв)", self.duration)
        layout.addRow("Календар", self.calendar_combo)
        buttons = QHBoxLayout()
        ok_button = QPushButton("Створити")
        cancel_button = QPushButton("Скасувати")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        layout.addRow(buttons)

    def get_values(self):
        start = self.date_time.dateTime().toPython()
        end = start + timedelta(minutes=self.duration.value())
        calendar_id = self.calendar_combo.currentText()
        return start, end, calendar_id, self.duration.value()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("StoDesktop")
        self.app_dir = get_app_dir()
        self.data_dir = os.path.join(self.app_dir, "data")
        self.logs_dir = os.path.join(self.app_dir, "logs")
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        self.db_path = os.path.join(self.data_dir, "app.db")
        self.config_path = os.path.join(self.data_dir, "config.json")

        self.config = AppConfig.load(self.config_path)
        self.db = Database(self.db_path)

        self.log_emitter = LogEmitter()
        self.log_emitter.message.connect(self._append_log)
        self._setup_logging()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.chat_tabs = QTabWidget()
        self.chat_list = QListWidget()
        self.messages_by_chat = {}

        self.calendar_tab = QWidget()
        self.settings_tab = QWidget()
        self.logs_tab = QWidget()

        self._build_chat_tab()
        self._build_calendar_tab()
        self._build_settings_tab()
        self._build_logs_tab()

        self.tabs.addTab(self.chat_container, "Чати")
        self.tabs.addTab(self.calendar_tab, "Календар")
        self.tabs.addTab(self.settings_tab, "Налаштування")
        self.tabs.addTab(self.logs_tab, "Логи/Помилки")

        self._load_chats()
        self._validate_config(initial=True)
        self._start_api_server()

    def _setup_logging(self):
        log_path = os.path.join(self.logs_dir, "app.log")
        logging.basicConfig(
            level=logging.INFO,
            handlers=[logging.FileHandler(log_path, encoding="utf-8")],
            format="%(asctime)s [%(levelname)s] %(message)s",
        )
        handler = QtLogHandler(self.log_emitter)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logging.getLogger().addHandler(handler)

    def _build_chat_tab(self):
        self.chat_container = QWidget()
        layout = QHBoxLayout(self.chat_container)
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.chat_list)
        splitter.addWidget(self.chat_tabs)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)
        self.chat_list.itemClicked.connect(self._open_chat_tab)

    def _build_calendar_tab(self):
        layout = QVBoxLayout(self.calendar_tab)
        controls = QHBoxLayout()
        self.calendar_filter = QComboBox()
        self.calendar_period = QComboBox()
        self.calendar_period.addItems(["Today", "Week"])
        refresh_button = QPushButton("Оновити")
        refresh_button.clicked.connect(self._load_calendar_events)
        controls.addWidget(QLabel("Календар"))
        controls.addWidget(self.calendar_filter)
        controls.addWidget(QLabel("Період"))
        controls.addWidget(self.calendar_period)
        controls.addWidget(refresh_button)
        layout.addLayout(controls)
        self.calendar_events_list = QListWidget()
        layout.addWidget(self.calendar_events_list)

    def _build_settings_tab(self):
        layout = QVBoxLayout(self.settings_tab)
        form = QFormLayout()
        self.token_input = QLineEdit(self.config.telegram_bot_token)
        self.secret_input = QLineEdit(self.config.shared_secret)
        self.port_input = QLineEdit(str(self.config.local_api_port))
        self.creds_input = QLineEdit(self.config.google_creds_path)
        browse_button = QPushButton("Обрати файл")
        browse_button.clicked.connect(self._browse_creds)
        creds_layout = QHBoxLayout()
        creds_layout.addWidget(self.creds_input)
        creds_layout.addWidget(browse_button)
        form.addRow("Telegram Bot Token", self.token_input)
        form.addRow("Shared Secret", self.secret_input)
        form.addRow("Local API Port", self.port_input)
        form.addRow("Google creds path", creds_layout)

        layout.addLayout(form)

        self.mapping_table = QTableWidget(0, 2)
        self.mapping_table.setHorizontalHeaderLabels(["service_type", "calendar_id"])
        layout.addWidget(QLabel("Mapping service_type -> calendar_id"))
        layout.addWidget(self.mapping_table)
        mapping_buttons = QHBoxLayout()
        add_row = QPushButton("Додати")
        remove_row = QPushButton("Видалити")
        add_row.clicked.connect(self._add_mapping_row)
        remove_row.clicked.connect(self._remove_mapping_row)
        mapping_buttons.addWidget(add_row)
        mapping_buttons.addWidget(remove_row)
        layout.addLayout(mapping_buttons)

        buttons = QHBoxLayout()
        save_button = QPushButton("Save")
        test_telegram = QPushButton("Test Telegram")
        test_google = QPushButton("Test Google Calendar")
        test_local = QPushButton("Test Local API")
        save_button.clicked.connect(self._save_settings)
        test_telegram.clicked.connect(self._test_telegram)
        test_google.clicked.connect(self._test_google)
        test_local.clicked.connect(self._test_local_api)
        buttons.addWidget(save_button)
        buttons.addWidget(test_telegram)
        buttons.addWidget(test_google)
        buttons.addWidget(test_local)
        layout.addLayout(buttons)

        self.test_status = QTextEdit()
        self.test_status.setReadOnly(True)
        layout.addWidget(self.test_status)

        self._load_mapping_table()

    def _build_logs_tab(self):
        layout = QVBoxLayout(self.logs_tab)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

    def _append_log(self, message: str):
        self.log_output.append(message)

    def _load_mapping_table(self):
        self.mapping_table.setRowCount(0)
        for mapping in self.config.service_calendar_mapping:
            row = self.mapping_table.rowCount()
            self.mapping_table.insertRow(row)
            self.mapping_table.setItem(row, 0, QTableWidgetItem(mapping.get("service_type", "")))
            self.mapping_table.setItem(row, 1, QTableWidgetItem(mapping.get("calendar_id", "")))

    def _add_mapping_row(self):
        row = self.mapping_table.rowCount()
        self.mapping_table.insertRow(row)

    def _remove_mapping_row(self):
        row = self.mapping_table.currentRow()
        if row >= 0:
            self.mapping_table.removeRow(row)

    def _browse_creds(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select creds.json", "", "JSON Files (*.json)")
        if path:
            self.creds_input.setText(path)

    def _save_settings(self):
        try:
            port = int(self.port_input.text())
        except ValueError:
            QMessageBox.warning(self, "Config", "Local API Port має бути числом")
            return
        mapping = []
        for row in range(self.mapping_table.rowCount()):
            service_item = self.mapping_table.item(row, 0)
            calendar_item = self.mapping_table.item(row, 1)
            if not service_item and not calendar_item:
                continue
            mapping.append(
                {
                    "service_type": service_item.text() if service_item else "",
                    "calendar_id": calendar_item.text() if calendar_item else "",
                }
            )

        self.config = AppConfig(
            telegram_bot_token=self.token_input.text().strip(),
            shared_secret=self.secret_input.text().strip(),
            local_api_port=port,
            google_creds_path=self.creds_input.text().strip(),
            service_calendar_mapping=mapping,
        )
        self.config.save(self.config_path)
        QMessageBox.information(self, "Config", "Збережено")
        self._validate_config()
        self._load_calendar_filters()
        self._restart_api_server()

    def _validate_config(self, initial=False):
        missing = self.config.validate()
        self.config_valid = len(missing) == 0
        if not self.config_valid:
            message = "CONFIG_MISSING: " + ", ".join(missing)
            logging.error(message)
            QMessageBox.warning(self, "Config", message)
            self.tabs.setCurrentWidget(self.settings_tab)
        self._update_action_state()
        if initial:
            self._load_calendar_filters()

    def _update_action_state(self):
        enabled = self.config_valid
        for idx in range(self.chat_tabs.count()):
            widget = self.chat_tabs.widget(idx)
            input_line = widget.findChild(QLineEdit, "message_input")
            send_button = widget.findChild(QPushButton, "send_button")
            schedule_button = widget.findChild(QPushButton, "schedule_button")
            if input_line:
                input_line.setEnabled(enabled)
            if send_button:
                send_button.setEnabled(enabled)
            if schedule_button:
                schedule_button.setEnabled(enabled)

    def _start_api_server(self):
        if not self.config.shared_secret:
            return
        self.api_server = LocalAPIServer(
            "127.0.0.1", self.config.local_api_port, self.config.shared_secret, self._handle_incoming
        )
        self.api_server.start()

    def _restart_api_server(self):
        if hasattr(self, "api_server") and self.api_server:
            self.api_server.stop()
        self._start_api_server()

    def _handle_incoming(self, payload: dict):
        chat_id = str(payload.get("chat_id"))
        user_name = payload.get("user_name", "Unknown")
        text = payload.get("text", "")
        ts = payload.get("ts", datetime.utcnow().isoformat())
        self.db.upsert_chat(chat_id, user_name)
        self.db.add_message(chat_id, "in", text, ts, "sent", json.dumps(payload))
        self._refresh_chat_list()
        self._append_message_to_ui(chat_id, f"{user_name}: {text}")

    def _load_chats(self):
        self._refresh_chat_list()

    def _refresh_chat_list(self):
        self.chat_list.clear()
        for chat_id, display_name, last_message, _ in self.db.get_chats():
            label = f"{display_name} ({chat_id})" if display_name else chat_id
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, chat_id)
            self.chat_list.addItem(item)

    def _open_chat_tab(self, item: QListWidgetItem):
        chat_id = item.data(Qt.UserRole)
        for idx in range(self.chat_tabs.count()):
            if self.chat_tabs.tabText(idx) == chat_id:
                self.chat_tabs.setCurrentIndex(idx)
                return
        tab = QWidget()
        layout = QVBoxLayout(tab)
        messages = QListWidget()
        input_layout = QHBoxLayout()
        input_line = QLineEdit()
        input_line.setObjectName("message_input")
        send_button = QPushButton("Надіслати")
        send_button.setObjectName("send_button")
        schedule_button = QPushButton("Запланувати час")
        schedule_button.setObjectName("schedule_button")
        send_button.clicked.connect(lambda: self._send_chat_message(chat_id, input_line, messages))
        schedule_button.clicked.connect(lambda: self._schedule_for_chat(chat_id))
        input_layout.addWidget(input_line)
        input_layout.addWidget(send_button)
        input_layout.addWidget(schedule_button)
        layout.addWidget(messages)
        layout.addLayout(input_layout)
        tab.setLayout(layout)
        self.chat_tabs.addTab(tab, chat_id)
        self.chat_tabs.setCurrentWidget(tab)

        self.messages_by_chat[chat_id] = messages
        for direction, text, ts, status in self.db.get_messages(chat_id):
            prefix = "You" if direction == "out" else "Client"
            messages.addItem(f"{ts} {prefix}: {text} ({status})")
        self._update_action_state()

    def _append_message_to_ui(self, chat_id: str, text: str):
        messages = self.messages_by_chat.get(chat_id)
        if messages:
            messages.addItem(text)

    def _send_chat_message(self, chat_id: str, input_line: QLineEdit, messages: QListWidget):
        if not self.config_valid:
            QMessageBox.warning(self, "Config", "Заповніть налаштування")
            return
        text = input_line.text().strip()
        if not text:
            return
        success, info = send_message(self.config.telegram_bot_token, chat_id, text)
        status = "sent" if success else "failed"
        ts = datetime.utcnow().isoformat()
        self.db.add_message(chat_id, "out", text, ts, status, info)
        messages.addItem(f"{ts} You: {text} ({status})")
        if not success:
            logging.error("Send failed: %s", info)
        input_line.clear()

    def _schedule_for_chat(self, chat_id: str):
        if not self.config_valid:
            QMessageBox.warning(self, "Config", "Заповніть налаштування")
            return
        calendar_ids = [m.get("calendar_id") for m in self.config.service_calendar_mapping if m.get("calendar_id")]
        if not calendar_ids:
            QMessageBox.warning(self, "Config", "Немає calendar_id у mapping")
            return
        dialog = ScheduleDialog(calendar_ids)
        if dialog.exec() != QDialog.Accepted:
            return
        start, end, calendar_id, duration = dialog.get_values()
        if has_conflict(self.config.google_creds_path, calendar_id, start, end):
            QMessageBox.warning(self, "Calendar", "Час зайнятий")
            return
        event_id = create_event(
            self.config.google_creds_path,
            calendar_id,
            f"Service chat {chat_id}",
            start,
            end,
        )
        self.db.add_calendar_event(chat_id, calendar_id, event_id, start.isoformat(), end.isoformat())
        confirmation = f"Запис підтверджено: {start.strftime('%Y-%m-%d %H:%M')}, {duration} хв"
        success, info = send_message(self.config.telegram_bot_token, chat_id, confirmation)
        if not success:
            logging.error("Send confirmation failed: %s", info)
        QMessageBox.information(self, "Calendar", "Подію створено")
        self._load_calendar_events()

    def _load_calendar_filters(self):
        self.calendar_filter.clear()
        for mapping in self.config.service_calendar_mapping:
            calendar_id = mapping.get("calendar_id")
            if calendar_id:
                self.calendar_filter.addItem(calendar_id)

    def _load_calendar_events(self):
        if not self.config_valid:
            return
        calendar_id = self.calendar_filter.currentText()
        if not calendar_id:
            return
        now = datetime.utcnow()
        if self.calendar_period.currentText() == "Today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        else:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        events = list_events(self.config.google_creds_path, calendar_id, start, end)
        self.calendar_events_list.clear()
        for event in events:
            summary = event.get("summary", "(no title)")
            start_time = event.get("start", {}).get("dateTime", "")
            self.calendar_events_list.addItem(f"{start_time} - {summary}")

    def _test_telegram(self):
        ok, info = test_token(self.token_input.text().strip())
        status = "OK" if ok else f"FAIL: {info}"
        self.test_status.append(f"Telegram: {status}")

    def _test_google(self):
        try:
            test_access(self.creds_input.text().strip())
            self.test_status.append("Google Calendar: OK")
        except Exception as exc:
            self.test_status.append(f"Google Calendar: FAIL: {exc}")

    def _test_local_api(self):
        import requests
        import hmac
        sample = {
            "chat_id": "test",
            "user_name": "Test",
            "text": "Ping",
            "ts": datetime.utcnow().isoformat(),
            "message_id": "0",
        }
        body = json.dumps(sample).encode("utf-8")
        secret = self.secret_input.text().strip().encode("utf-8")
        signature = hmac.new(secret, body, "sha256").hexdigest()
        try:
            response = requests.post(
                f"http://127.0.0.1:{self.port_input.text().strip()}/api/telegram/incoming",
                data=body,
                headers={"Content-Type": "application/json", "X-Signature": signature},
                timeout=2,
            )
            if response.status_code == 200:
                self.test_status.append("Local API: OK")
            else:
                self.test_status.append(f"Local API: FAIL: {response.text}")
        except Exception as exc:
            self.test_status.append(f"Local API: FAIL: {exc}")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
