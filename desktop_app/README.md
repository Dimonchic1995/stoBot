# StoDesktop (PySide6)

## Run locally
```bash
python main.py
```

## Build portable (onedir)
```bash
pyinstaller sto_desktop.spec
```

Output will be in `dist/StoDesktop/` with `StoDesktop.exe`.

### Portable layout expectations
Keep these files beside the exe:
- `data/config.json`
- `data/app.db`
- `logs/app.log`
- `creds.json` (external, not embedded)
