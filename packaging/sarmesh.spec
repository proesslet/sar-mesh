# PyInstaller spec for SARMesh.
#
# Built as onedir rather than onefile: QtWebEngine spawns a helper process
# (QtWebEngineProcess) that has to find Qt's resources on disk, and onefile's
# extract-to-temp behaviour makes that both fragile and slow to start. The
# directory is what gets wrapped in an installer / AppImage / .deb anyway.

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

PROJECT_ROOT = Path(SPECPATH).parent
STATIC_DIR = PROJECT_ROOT / "src" / "sarmesh" / "web" / "static"

if not (STATIC_DIR / "index.html").is_file():
    raise SystemExit(
        "Frontend not built. Run `npm --prefix frontend run build` first -- "
        "without it the packaged app would start with no UI to serve."
    )

datas = [
    # server.py resolves this as Path(__file__).parent / "static", which under
    # PyInstaller lands at <bundle>/sarmesh/web/static.
    (str(STATIC_DIR), "sarmesh/web/static"),
]

# Meshtastic ships protobuf modules and version metadata it reads at runtime.
datas += collect_data_files("meshtastic")

hiddenimports = [
    "meshtastic.serial_interface",
    "meshtastic.tcp_interface",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
]

# Qt modules SARMesh never touches. QtWebEngine itself pulls QtQuick, QtQml,
# QtNetwork and QtWebChannel, so those must stay.
excludes = [
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNfc",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "tkinter",
]

# Payload Qt ships that a single-purpose offline app never reads. QtWebEngine
# still needs its own core resources and the en-US locale, so those stay.
PRUNE = [
    "PySide6/Qt/translations/qtwebengine_locales/*",
    "PySide6/Qt/translations/*.qm",
    "PySide6/Qt/resources/qtwebengine_devtools_resources.pak",
    "PySide6/Qt/qml/*",
]

KEEP = [
    "PySide6/Qt/translations/qtwebengine_locales/en-US.pak",
]


def _prune(entries):
    from fnmatch import fnmatch

    kept = []

    for entry in entries:
        dest = entry[0].replace("\\", "/")

        if any(fnmatch(dest, pattern) for pattern in KEEP):
            kept.append(entry)
            continue

        if any(fnmatch(dest, pattern) for pattern in PRUNE):
            continue

        kept.append(entry)

    return kept


a = Analysis(
    [str(PROJECT_ROOT / "packaging" / "entry.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

a.datas = _prune(a.datas)
a.binaries = _prune(a.binaries)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="sarmesh",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="sarmesh",
)
