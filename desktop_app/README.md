# StoDesktop

## Запуск локально

```bash
python app.py
```

## PyInstaller (portable onedir)

```bash
pyinstaller --clean --noconfirm pyinstaller.spec
```

Після збірки поруч з `StoDesktop.exe` мають бути:

- `./data/config.json`
- `./data/app.db` (створюється автоматично при старті)
- `./logs/app.log` (створюється автоматично)
- `creds.json` (service account, зовнішній файл)

Не хардкодьте токени чи секрети у коді — використовуйте `data/config.json`.
