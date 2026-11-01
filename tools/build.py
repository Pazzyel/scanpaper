"""Native Windows, macOS and Linux builds with archive round-trip verification."""
import argparse
import hashlib
from importlib.metadata import distribution
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scanpaper import __version__ as VERSION
from tools.packaging_support import create_archive, extract_archive, host_target, smoke_environment
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
             'Noto Sans CJK SC: SIL Open Font License 1.1 (see NotoSansCJK/OFL.txt).',
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
    python_license = next((path for path in (Path(sys.base_prefix) / 'LICENSE.txt',
        Path(sys.base_prefix) / 'LICENSE', Path(sys.base_prefix) / 'lib/python3.12/LICENSE.txt')
        if path.is_file()), None)
    if python_license is None:
        import sysconfig
        python_license = Path(sysconfig.get_path('stdlib')) / 'LICENSE.txt'
    if not python_license.is_file():
        raise RuntimeError('Python license file was not found in this interpreter distribution')
    shutil.copy2(python_license, folder / 'Python-LICENSE.txt')
    (folder / 'NotoSansCJK').mkdir(exist_ok=True)
    shutil.copy2(ROOT / 'assets/fonts/OFL.txt', folder / 'NotoSansCJK/OFL.txt')
    lines.extend(['', f'Python {platform.python_version()} (PSF license and bundled notices).', '',
        'PyInstaller is a build tool; its bootloader distribution exception applies.', '',
        'Qt / PySide6 / Shiboken6: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only.',
        'This distribution uses the LGPL option. Libraries are dynamically linked in the application bundle.',
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
    image = QImage(1024, 1024, QImage.Format.Format_RGBA8888)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    QSvgRenderer(str(ROOT / 'assets' / 'scanpaper.svg')).render(painter)
    painter.end()
    png = ROOT / 'assets' / 'scanpaper.png'
    image.save(str(png))
    with Image.open(png) as icon:
        icon.save(ROOT / 'assets' / 'scanpaper.ico', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        icon.save(ROOT / 'assets' / 'scanpaper.icns', format='ICNS')


def source_archive(destination):
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in ('scanpaper', 'tests', 'tools', 'assets', 'licenses', '.github'):
            for path in sorted((ROOT / name).rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts:
                    archive.write(path, Path('ScanPaper-source') / path.relative_to(ROOT))
        for name in ('main.py', 'README.md', '使用说明.txt', 'LICENSE', 'requirements.txt',
                     'requirements-build.txt', 'ScanPaper.spec', '.gitignore'):
            archive.write(ROOT / name, Path('ScanPaper-source') / name)


def verify_executable(executable, directory, env):
    directory.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([str(executable), '--self-test', str(directory)],
                            cwd=executable.parent, env=env, capture_output=True, timeout=180)
    (directory / 'process.log').write_bytes(result.stdout + result.stderr)
    report_path = directory / 'self-test.json'
    if not report_path.exists():
        raise RuntimeError(f'Packaged executable exited {result.returncode}; see {directory / "process.log"}')
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if result.returncode or not report['passed']:
        raise RuntimeError(f'Packaged self-test failed: {report}')
    return report


def build():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-smoke', action='store_true', help='Also test the native Qt desktop plugin; Linux needs DISPLAY/Xvfb')
    parser.add_argument('--skip-source', action='store_true', help='Do not generate a duplicate source ZIP in a build matrix')
    args = parser.parse_args()
    target = host_target()
    print(f'Building ScanPaper {VERSION} for {target.label}', flush=True)
    prepare_licenses()
    prepare_icon()
    run(sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v')
    run(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', ROOT / 'ScanPaper.spec')
    portable = ROOT / 'dist' / target.folder
    if target.system != 'macOS':
        shutil.copy2(ROOT / '使用说明.txt', portable / '使用说明.txt')
        shutil.copy2(ROOT / 'LICENSE', portable / 'LICENSE.txt')
        shutil.copytree(ROOT / 'licenses', portable / 'licenses', dirs_exist_ok=True)
    else:
        run('codesign', '--verify', '--deep', '--strict', portable)
    if not any(portable.rglob(target.plugin)):
        raise RuntimeError(f'Missing Qt platform plugin: {target.plugin}')
    if target.system == 'Windows' and any(
        path.name.lower() in {'icu.dll', 'icuuc.dll', 'icuin.dll', 'icudt.dll', 'icuio.dll'}
        for path in portable.rglob('*.dll')
    ):
        raise RuntimeError('A bundled ICU DLL would shadow the Windows system ICU library')
    release = ROOT / 'release'
    release.mkdir(exist_ok=True)
    archive_path = release / f'ScanPaper-{VERSION}-{target.label}{target.suffix}'
    create_archive(portable, archive_path, target)
    artifacts = ROOT / 'artifacts'
    artifacts.mkdir(exist_ok=True)
    extracted = Path(tempfile.mkdtemp(prefix='portable-check-', dir=artifacts))
    extract_archive(archive_path, extracted, target)
    executable = extracted / target.executable
    env = smoke_environment(target)
    report = verify_executable(executable, extracted / 'verification', env)
    if args.native_smoke:
        env['QT_QPA_PLATFORM'] = target.native_qt_platform
        verify_executable(executable, extracted / 'verification/native', env)
        report['native_platform_verified'] = target.native_qt_platform
    verification = release / 'verification' / target.label
    shutil.copytree(extracted / 'verification', verification, dirs_exist_ok=True)
    report['environment'] = 'Archive extracted separately; system-only PATH; unreachable HTTP/HTTPS proxy'
    report['versions'] = {name: distribution(name).version for name in PACKAGES}
    report['python'] = platform.python_version()
    report['target'] = target.label
    (verification / 'self-test.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    output_files = [archive_path]
    if not args.skip_source:
        source_zip = release / f'ScanPaper-{VERSION}-source.zip'
        source_archive(source_zip)
        output_files.append(source_zip)
    hashes = []
    for path in output_files:
        with path.open('rb') as stream:
            hashes.append(f'{hashlib.file_digest(stream, "sha256").hexdigest()}  {path.name}')
    (release / f'SHA256SUMS-{target.label}.txt').write_text('\n'.join(hashes) + '\n', encoding='ascii')
    print(f'PORTABLE: {archive_path}\nSIZE: {archive_path.stat().st_size / 1048576:.1f} MiB', flush=True)


if __name__ == '__main__':
    build()
