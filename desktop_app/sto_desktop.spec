# PyInstaller build spec for StoDesktop
# Build: pyinstaller --noconfirm --clean sto_desktop.spec

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("google")

block_cipher = None


a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("../data/config.json", "data"),
        ("../data/app.db", "data"),
        ("../logs/app.log", "logs"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="StoDesktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="StoDesktop",
)
