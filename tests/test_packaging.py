import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from tools.packaging_support import (Target, create_archive, extract_archive,
                                     host_target, smoke_environment)


class PackagingTests(unittest.TestCase):
    def test_supported_hosts_have_native_launch_paths(self):
        for system, machine, label, binary, suffix in [
            ('Windows', 'AMD64', 'Windows-x64', 'ScanPaper/ScanPaper.exe', '.zip'),
            ('Darwin', 'arm64', 'macOS-arm64', 'ScanPaper.app/Contents/MacOS/ScanPaper', '.zip'),
            ('Darwin', 'x86_64', 'macOS-x64', 'ScanPaper.app/Contents/MacOS/ScanPaper', '.zip'),
            ('Linux', 'x86_64', 'Linux-x64', 'ScanPaper/ScanPaper', '.tar.gz'),
        ]:
            target = host_target(system, machine)
            self.assertEqual(target.label, label)
            self.assertEqual(target.executable.as_posix(), binary)
            self.assertEqual(target.suffix, suffix)

    def test_unsupported_host_is_rejected_before_building(self):
        for system, machine in [('Linux', 'i686'), ('Linux', 'aarch64'), ('Windows', 'ARM64'), ('FreeBSD', 'x86_64')]:
            with self.assertRaisesRegex(RuntimeError, 'Unsupported build host'):
                host_target(system, machine)

    def test_windows_archive_round_trip_including_unicode(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app = root / 'ScanPaper'
            app.mkdir()
            (app / 'ScanPaper.exe').write_bytes(b'test executable')
            (app / '使用说明.txt').write_text('本地处理', encoding='utf-8')
            archive = root / 'app.zip'
            target = Target('Windows', 'x64')
            create_archive(app, archive, target)
            extract_archive(archive, root / 'unpacked', target)
            self.assertEqual((root / 'unpacked/ScanPaper/使用说明.txt').read_text(encoding='utf-8'), '本地处理')

    @unittest.skipIf(os.name == 'nt', 'POSIX executable modes and symlinks are verified on Linux/macOS')
    def test_linux_archive_keeps_executable_and_shared_library_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app = root / 'ScanPaper'
            app.mkdir()
            executable = app / 'ScanPaper'
            executable.write_bytes(b'executable')
            executable.chmod(0o755)
            (app / 'libQt6Core.so.6.12.0').write_bytes(b'shared library')
            (app / 'libQt6Core.so.6').symlink_to('libQt6Core.so.6.12.0')
            archive = root / 'app.tar.gz'
            target = Target('Linux', 'x64')
            create_archive(app, archive, target)
            extract_archive(archive, root / 'unpacked', target)
            restored = root / 'unpacked/ScanPaper'
            self.assertTrue((restored / 'ScanPaper').stat().st_mode & stat.S_IXUSR)
            self.assertTrue((restored / 'libQt6Core.so.6').is_symlink())
            self.assertEqual((restored / 'libQt6Core.so.6').read_bytes(), b'shared library')

    def test_smoke_environment_excludes_development_dependencies(self):
        with patch.dict(os.environ, {'PYTHONPATH': '/developer/python', 'PYTHONHOME': '/developer',
                                      'LD_LIBRARY_PATH': '/developer/libs', 'QT_PLUGIN_PATH': '/developer/qt',
                                      'HOME': '/home/test', 'DISPLAY': ':99'}):
            env = smoke_environment(Target('Linux', 'x64'))
        for key in ('PYTHONPATH', 'PYTHONHOME', 'LD_LIBRARY_PATH', 'QT_PLUGIN_PATH'):
            self.assertNotIn(key, env)
        self.assertEqual(env['HOME'], '/home/test')
        self.assertEqual(env['DISPLAY'], ':99')
        self.assertNotIn('developer', env['PATH'])
        self.assertEqual(env['QT_QPA_PLATFORM'], 'offscreen')


if __name__ == '__main__':
    unittest.main()
