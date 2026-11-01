# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / 'assets'), 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
              'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtPdf',
              'PySide6.QtPdfWidgets', 'tkinter', 'pypdf'],
    noarchive=False,
    optimize=0,
)

# This Qt build imports Windows' unversioned ICU C ABI. An unrelated ICU
# found on the build machine's PATH (e.g. Poppler) has versioned exports and
# shadows the OS library, causing "procedure not found" when QtCore loads.
# Windows 10/11 provide these system DLLs; never redistribute other copies.
windows_icu = {'icu.dll', 'icuuc.dll', 'icuin.dll', 'icudt.dll', 'icuio.dll'}
a.binaries = [entry for entry in a.binaries
              if Path(entry[0]).name.lower() not in windows_icu]

pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='ScanPaper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=[str(ROOT / 'assets' / 'scanpaper.ico')],
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False,
    upx=False,
    name='ScanPaper',
)
