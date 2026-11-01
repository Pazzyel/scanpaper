# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import runpy
import sys

ROOT = Path(SPECPATH)
VERSION = runpy.run_path(str(ROOT / 'scanpaper' / '__init__.py'))['__version__']
is_mac = sys.platform == 'darwin'
linux_libraries = []
if sys.platform == 'linux':
    # Include XCB helpers absent from some otherwise complete Linux desktops.
    library_root = Path('/usr/lib/x86_64-linux-gnu')
    for pattern in ('libxcb*.so.[0-9]', 'libxkbcommon*.so.[0-9]', 'libX11-xcb.so.[0-9]',
                    'libXau.so.[0-9]', 'libXdmcp.so.[0-9]'):
        linux_libraries.extend((str(path), '.') for path in sorted(library_root.glob(pattern)))

mac_documents = [(str(ROOT / 'licenses'), 'licenses'),
                 (str(ROOT / '使用说明.txt'), '.'), (str(ROOT / 'LICENSE'), '.')]
a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=linux_libraries,
    datas=[(str(ROOT / 'assets'), 'assets')] + (mac_documents if is_mac else []),
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

# Qt on Windows imports the native unversioned ICU ABI. Never let unrelated
# build-machine ICU DLLs shadow it. Linux/macOS retain their own ICU libraries.
if sys.platform == 'win32':
    windows_icu = {'icu.dll', 'icuuc.dll', 'icuin.dll', 'icudt.dll', 'icuio.dll'}
    a.binaries = [entry for entry in a.binaries
                  if Path(entry[0]).name.lower() not in windows_icu]

pyz = PYZ(a.pure)
icon = 'scanpaper.icns' if is_mac else 'scanpaper.ico'
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='ScanPaper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=sys.platform == 'linux',
    disable_windowed_traceback=False,
    icon=[str(ROOT / 'assets' / icon)] if sys.platform != 'linux' else None,
    target_arch=None,
    codesign_identity=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='ScanPaper')
if is_mac:
    app = BUNDLE(
        coll,
        name='ScanPaper.app',
        icon=str(ROOT / 'assets' / 'scanpaper.icns'),
        bundle_identifier='io.github.pazzyel.scanpaper',
        info_plist={
            'CFBundleShortVersionString': VERSION,
            'CFBundleVersion': VERSION,
            'LSMinimumSystemVersion': '14.4',
            'NSHighResolutionCapable': True,
            'NSPrincipalClass': 'NSApplication',
        },
    )
