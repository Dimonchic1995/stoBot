# Sto Desktop build (PyInstaller)

```bash
cd desktop_app
python -m PyInstaller --clean --onedir pyinstaller.spec
```

## Portable bundle layout

After build, place files next to the executable:

```
StoDesktop/
  StoDesktop.exe
  data/
    config.json
    app.db
  logs/
    app.log
  creds.json
```

*`creds.json` should be provided externally and never embedded into the bundle.*
