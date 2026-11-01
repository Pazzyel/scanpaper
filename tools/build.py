"""Reproducible Windows x64 portable build, with isolated executable smoke test."""
import hashlib
from importlib.metadata import distribution
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parent.parent
VERSION = '1.0.0'
NAME = f'ScanPaper-{VERSION}-Windows-x64'
PACKAGES = ['PySide6_Essentials', 'shiboken6', 'Pillow', 'numpy',
            'opencv-python-headless', 'reportlab', 'charset-normalizer', 'pyinstaller']


def run(*args, **kwargs):
    print('Running:', ' '.join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), cwd=ROOT, check=True, **kwargs)


def prepare_licenses():
    folder = ROOT / 'licenses'
    folder.mkdir(exist_ok=True)
    lines = ['ScanPaper third-party notices', '',
             'Application source: MIT (see LICENSE).',
             'All processing is local. No online service is required.', '',
             'Runtime components and original license files:']
    for name in PACKAGES:
        package = distribution(name)
        lines.append(f'{name} {package.version}')
        for entry in package.files or []:
            if any(token in str(entry).lower() for token in ('license', 'copying', 'notice')):
                source = Path(package.locate_file(entry))
                if source.is_file():
                    destination = folder / name / str(entry)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
        # Preserve upstream metadata and license declarations as well.
        (folder / name).mkdir(exist_ok=True)
        (folder / name / 'METADATA.txt').write_text(package.read_text('METADATA') or '', encoding='utf-8')
    shutil.copy2(Path(sys.base_prefix) / 'LICENSE.txt', folder / 'Python-LICENSE.txt')
    lines.extend(['', f'Python {platform.python_version()} (PSF license and bundled notices).', '',
        'PyInstaller is a build tool; its bootloader distribution exception applies.', '',
        'Qt / PySide6 / Shiboken6: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only.',
        'This distribution uses the LGPL option. Libraries are supplied separately in _internal.',
        'You may replace or relink these libraries and debug modifications under the applicable licenses.',
        'Application source is supplied in the matching source ZIP. No restriction is imposed on',
        'reverse engineering for debugging modifications to LGPL-covered libraries.', '',
        'LGPL-3.0.txt and GPL-3.0.txt contain the complete license texts.',
        'Corresponding upstream source and build information:',
        'https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/',
        'https://code.qt.io/cgit/pyside/pyside-setup.git/?h=v6.12.0',
        'https://download.qt.io/official_releases/qt/6.12/6.12.0/single/',
        'https://code.qt.io/cgit/qt/qtbase.git/?h=v6.12.0',
        'https://code.qt.io/cgit/qt/qtsvg.git/?h=v6.12.0',
        'https://doc.qt.io/qt-6/licenses-used-in-qt.html',
        'https://www.python.org/downloads/source/',
        'https://github.com/python-pillow/Pillow',
        'https://github.com/numpy/numpy',
        'https://github.com/opencv/opencv',
        'https://github.com/opencv/opencv-python',
        'https://github.com/pyinstaller/pyinstaller',
        'https://hg.reportlab.com/hg-public/reportlab/', '',
        'The upstream license files are retained unmodified, including alternative commercial',
        'license references supplied by upstream. These references do not grant a commercial license.'])
    (folder / 'THIRD-PARTY.txt').write_text('\n'.join(lines), encoding='utf-8')
    for required in ('LGPL-3.0.txt', 'GPL-3.0.txt'):
        if not (folder / required).is_file():
            raise RuntimeError(f'Missing checked-in license: {required}')


def prepare_icon():
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import QApplication
    from PIL import Image
    app = QApplication.instance() or QApplication([])
    image = QImage(256, 256, QImage.Format.Format_RGBA8888)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    QSvgRenderer(str(ROOT / 'assets' / 'scanpaper.svg')).render(painter)
    painter.end()
    png = ROOT / 'assets' / 'scanpaper.png'
    image.save(str(png))
    with Image.open(png) as icon:
        icon.save(ROOT / 'assets' / 'scanpaper.ico', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def zip_folder(source, destination):
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(source.rglob('*')):
            if path.is_file():
                archive.write(path, Path(source.name) / path.relative_to(source))


def build():
    if sys.platform != 'win32' or platform.architecture()[0] != '64bit':
        raise RuntimeError('Build on Windows x64 with Python 3.12.')
    prepare_licenses()
    prepare_icon()
    run(sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v')
    run(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', ROOT / 'ScanPaper.spec')
    portable = ROOT / 'dist' / 'ScanPaper'
    shutil.copy2(ROOT / '使用说明.txt', portable / '使用说明.txt')
    shutil.copy2(ROOT / 'LICENSE', portable / 'LICENSE.txt')
    shutil.copytree(ROOT / 'licenses', portable / 'licenses', dirs_exist_ok=True)
    # qwindows is mandatory for normal desktop use; offscreen supports built-in QA.
    platforms = portable / '_internal' / 'PySide6' / 'plugins' / 'platforms'
    for name in ('qwindows.dll', 'qoffscreen.dll'):
        if not (platforms / name).is_file():
            raise RuntimeError(f'Missing Qt platform plugin: {name}')
    if any(path.name.lower() in {'icu.dll', 'icuuc.dll', 'icuin.dll', 'icudt.dll', 'icuio.dll'}
           for path in portable.rglob('*.dll')):
        raise RuntimeError('A bundled ICU DLL would shadow the Windows system ICU library')
    release = ROOT / 'release'
    release.mkdir(exist_ok=True)
    archive_path = release / f'{NAME}.zip'
    zip_folder(portable, archive_path)
    # Verify the actual ZIP, extracted elsewhere, without Python/venv on PATH.
    extracted = ROOT / 'artifacts' / f'portable-check-{int(time.time())}'
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(extracted)
    executable = extracted / 'ScanPaper' / 'ScanPaper.exe'
    output = extracted / 'verification'
    env = {key: value for key, value in os.environ.items()
           if key.upper() in {'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'USERPROFILE',
                              'APPDATA', 'LOCALAPPDATA', 'COMSPEC'}}
    env['PATH'] = str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'System32')
    env['HTTP_PROXY'] = env['HTTPS_PROXY'] = 'http://127.0.0.1:9'
    env['QT_QPA_PLATFORM'] = 'offscreen'
    subprocess.run([str(executable), '--self-test', str(output)], cwd=extracted,
                   env=env, check=True, timeout=180)
    result = json.loads((output / 'self-test.json').read_text(encoding='utf-8'))
    if not result['passed']:
        raise RuntimeError(result)
    verification = release / 'verification'
    shutil.copytree(output, verification, dirs_exist_ok=True)
    result['environment'] = 'ZIP extracted to a separate directory; system-only PATH; unreachable HTTP/HTTPS proxy'
    result['versions'] = {name: distribution(name).version for name in PACKAGES}
    result['python'] = platform.python_version()
    (verification / 'self-test.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    source_zip = release / 'ScanPaper-1.0.0-source.zip'
    with zipfile.ZipFile(source_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in ('scanpaper', 'tests', 'tools', 'assets', 'licenses'):
            for path in sorted((ROOT / name).rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts:
                    archive.write(path, Path('ScanPaper-source') / path.relative_to(ROOT))
        for name in ('main.py', 'README.md', '使用说明.txt', 'LICENSE', 'requirements.txt', 'requirements-build.txt', 'ScanPaper.spec', '.gitignore'):
            archive.write(ROOT / name, Path('ScanPaper-source') / name)
    hashes = []
    for path in (archive_path, source_zip):
        with path.open('rb') as stream:
            hashes.append(f'{hashlib.file_digest(stream, "sha256").hexdigest()}  {path.name}')
    (release / 'SHA256SUMS.txt').write_text('\n'.join(hashes) + '\n', encoding='ascii')
    print(f'PORTABLE: {archive_path}\nSOURCE: {source_zip}\nSIZE: {archive_path.stat().st_size / 1048576:.1f} MiB', flush=True)


if __name__ == '__main__':
    build()
