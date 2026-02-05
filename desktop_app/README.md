# StoDesktop (PySide6)

## Запуск
```bash
python app.py
```

## Конфіг
Portable файли зберігаються поруч із застосунком:
- `./data/config.json`
- `./data/app.db`
- `./logs/app.log`

## PyInstaller
```bash
pyinstaller --noconfirm --clean sto_desktop.spec
```
Після збірки поруч з `StoDesktop.exe` мають бути папки `data/` і `logs/`, а також `creds.json` (зовнішній файл, не вшивається).
