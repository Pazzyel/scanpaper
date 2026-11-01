"""Archive and host selection rules; no GUI or build dependencies."""
from dataclasses import dataclass
import os
from pathlib import Path
import platform
import subprocess
import tarfile
import zipfile


@dataclass(frozen=True)
class Target:
    system: str
    arch: str

    @property
    def label(self):
        return f'{self.system}-{self.arch}'

    @property
    def suffix(self):
        return '.tar.gz' if self.system == 'Linux' else '.zip'

    @property
    def folder(self):
        return 'ScanPaper.app' if self.system == 'macOS' else 'ScanPaper'

    @property
    def executable(self):
        if self.system == 'macOS':
            return Path(self.folder) / 'Contents/MacOS/ScanPaper'
        return Path(self.folder) / ('ScanPaper.exe' if self.system == 'Windows' else 'ScanPaper')

    @property
    def plugin(self):
        return {'Windows': 'qwindows.dll', 'macOS': 'libqcocoa.dylib', 'Linux': 'libqxcb.so'}[self.system]

    @property
    def native_qt_platform(self):
        return {'Windows': 'windows', 'macOS': 'cocoa', 'Linux': 'xcb'}[self.system]


def host_target(system=None, machine=None):
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()
    arch = {'amd64': 'x64', 'x86_64': 'x64', 'arm64': 'arm64', 'aarch64': 'arm64'}.get(machine)
    name = {'Windows': 'Windows', 'Darwin': 'macOS', 'Linux': 'Linux'}.get(system)
    if name is None or arch is None or (name != 'macOS' and arch != 'x64'):
        raise RuntimeError(f'Unsupported build host: {system} {machine}. Use Windows/Linux x64 or macOS x64/arm64.')
    return Target(name, arch)


def create_archive(source, destination, target):
    """Use native macOS ZIP and POSIX tar to preserve framework symlinks/modes."""
    if target.system == 'macOS':
        subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent',
                        str(source), str(destination)], check=True)
    elif target.system == 'Linux':
        with tarfile.open(destination, 'w:gz', dereference=False) as archive:
            archive.add(source, arcname=source.name)
    else:
        with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(source.rglob('*')):
                if path.is_file():
                    archive.write(path, Path(source.name) / path.relative_to(source))


def extract_archive(source, destination, target):
    destination.mkdir(parents=True, exist_ok=True)
    if target.system == 'macOS':
        subprocess.run(['ditto', '-x', '-k', str(source), str(destination)], check=True)
    elif target.system == 'Linux':
        with tarfile.open(source, 'r:gz') as archive:
            archive.extractall(destination, filter='data')
    else:
        with zipfile.ZipFile(source) as archive:
            archive.extractall(destination)


def smoke_environment(target):
    allowed = {'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'TMPDIR', 'USERPROFILE', 'APPDATA',
               'LOCALAPPDATA', 'COMSPEC', 'HOME', 'USER', 'LOGNAME', 'LANG', 'LC_ALL',
               'LC_CTYPE', 'DISPLAY', 'XAUTHORITY', 'WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR',
               'XDG_SESSION_TYPE', 'DBUS_SESSION_BUS_ADDRESS'}
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    env['PATH'] = (str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'System32')
                   if target.system == 'Windows' else '/usr/bin:/bin:/usr/sbin:/sbin')
    env['HTTP_PROXY'] = env['HTTPS_PROXY'] = 'http://127.0.0.1:9'
    env['QT_QPA_PLATFORM'] = 'offscreen'
    return env
