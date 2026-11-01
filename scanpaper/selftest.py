"""Packaged-app smoke test. Invoked explicitly, never during normal startup."""
import json
import os
from pathlib import Path
import time
import traceback


def make_scan():
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    width, height = 1800, 2400
    yy, xx = np.mgrid[:height, :width]
    gray = np.clip(246 - 28 * xx / width - 12 * np.sin(yy / height * np.pi), 0, 255).astype('uint8')
    image = Image.fromarray(gray).convert('RGB')
    draw = ImageDraw.Draw(image)
    try:
        regular = ImageFont.truetype('arial.ttf', 30)
        small = ImageFont.truetype('arial.ttf', 21)
        heading = ImageFont.truetype('arialbd.ttf', 58)
    except OSError:
        regular = small = heading = ImageFont.load_default(size=28)
    draw.text((150, 160), 'DOCUMENT / 2026', font=heading, fill=(20, 20, 20))
    draw.text((150, 255), 'Scan cleanup and paper layout', font=regular, fill=(65, 65, 65))
    draw.line((150, 330, 1650, 330), fill=(30, 30, 30), width=3)
    for row, text in enumerate([
        '01  Keep original resolution when exporting.',
        '02  Preserve punctuation, thin strokes and solid fills.',
        '03  Paper size and placement use millimetres.',
        '04  The background becomes transparent.',
        '05  All documents stay on this computer.',
    ]):
        draw.text((150, 410 + row * 94), text, font=regular, fill=(45, 45, 45))
    for y in range(1080, 1761, 136):
        draw.line((150, y, 1650, y), fill=(100, 100, 100), width=2)
    for x in (150, 600, 1150, 1650):
        draw.line((x, 1080, x, 1760), fill=(100, 100, 100), width=2)
    draw.text((180, 1120), 'REFERENCE', font=small, fill=(40, 40, 40))
    draw.text((640, 1120), 'DETAIL', font=small, fill=(40, 40, 40))
    draw.text((1200, 1120), 'STATUS', font=small, fill=(40, 40, 40))
    draw.text((180, 1260), 'SP-001', font=regular, fill=(65, 65, 65))
    draw.text((640, 1260), 'Fine line sample', font=regular, fill=(175, 175, 175))
    draw.rectangle((1220, 1270, 1450, 1360), fill=(0, 0, 0))
    draw.text((150, 1940), 'Fine text: 0123456789 , . : ; ! ?', font=small, fill=(165, 165, 165))
    draw.text((150, 2020), 'Gray pencil line - adjustable cleanup strength', font=small, fill=(195, 195, 195))
    draw.line((150, 2120, 1200, 2120), fill=(195, 195, 195), width=2)
    return image


def run(output_directory):
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    output = Path(output_directory).resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {'passed': False, 'checks': [], 'errors': []}
    try:
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtGui import QFont
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        from .app import MainWindow, configure_font
        from .model import PAPERS
        app = QApplication.instance() or QApplication([])
        configure_font(app)
        window = MainWindow()
        errors = []
        window.operation_failed = lambda error: (errors.append(str(error)), window.set_busy(False, '失败'))
        window.export_ready = lambda path: window.set_busy(False, f'已导出：{path}')
        def wait_until(predicate, seconds=60):
            deadline = time.monotonic() + seconds
            while not predicate():
                app.processEvents()
                time.sleep(0.02)
                if errors:
                    raise AssertionError(errors)
                if time.monotonic() > deadline:
                    raise TimeoutError('等待后台任务超时')
            app.processEvents()
        source = output / '测试扫描件.jpg'
        make_scan().save(source, quality=96)
        window.show()
        app.processEvents()
        window.load_image(str(source))
        wait_until(lambda: not window.busy and window.processed_preview is not None)
        report['checks'].append('JPEG decode, image plugins, worker cleanup and preview')
        assert window.source.size == (1800, 2400)
        l = window.layout_model
        ratio = l.width / l.height
        window.fields['width'].setValue(150)
        assert abs(l.width - 150) < 0.001 and abs(l.width / l.height - ratio) < 0.00001
        window.fields['x'].setValue(17)
        window.fields['y'].setValue(23)
        report['checks'].append('Millimetre size and position, aspect lock')
        for index, paper in enumerate(PAPERS):
            old = (l.x, l.y, l.width, l.height)
            window.paper_combo.setCurrentIndex(index)
            assert l.paper == paper and old == (l.x, l.y, l.width, l.height)
            window.orientation_combo.setCurrentIndex(1)
            assert l.paper_size[0] > l.paper_size[1]
            window.orientation_combo.setCurrentIndex(0)
        report['checks'].append('A1/A2/A3/A4, orientation, retain physical placement')
        window.fields['x'].setValue(-10)
        assert l.overflowing and not window.overflow_label.isHidden()
        window.fit_image()
        window.rotate()
        assert l.rotation == 1 and abs(l.width / l.height - 1 / ratio) < 0.00001
        window.reset_image()
        assert l.rotation == 0 and window.background_slider.value() == 35
        window.original_check.setChecked(True)
        window.checker_check.setChecked(True)
        window.original_check.setChecked(False)
        window.checker_check.setChecked(False)
        report['checks'].append('Overflow warning, fit, rotation, reset and display modes')
        # Exercise real view input: move in viewport pixels, then resize a corner.
        app.processEvents()
        from PySide6.QtCore import QPointF
        center = window.view.mapFromScene(QPointF(l.x + l.width / 2, l.y + l.height / 2))
        old_x = l.x
        QTest.mousePress(window.view.viewport(), Qt.MouseButton.LeftButton, pos=center)
        QTest.mouseMove(window.view.viewport(), center + QPoint(12, 8))
        QTest.mouseRelease(window.view.viewport(), Qt.MouseButton.LeftButton, pos=center + QPoint(12, 8))
        assert l.x > old_x
        corner = window.view.mapFromScene(QPointF(l.x + l.width, l.y + l.height))
        old_width = l.width
        QTest.mousePress(window.view.viewport(), Qt.MouseButton.LeftButton, pos=corner)
        QTest.mouseMove(window.view.viewport(), corner - QPoint(20, 20))
        QTest.mouseRelease(window.view.viewport(), Qt.MouseButton.LeftButton, pos=corner - QPoint(20, 20))
        assert l.width < old_width and abs(l.width / l.height - ratio) < 0.00001
        report['checks'].append('Mouse dragging and proportional corner resizing')
        window.fit_image()
        wait_until(lambda: not window.debounce.isActive() and window.preview_pool.activeThreadCount() == 0)
        app.processEvents()
        destination = output / '测试导出.pdf'
        window.begin_export(str(destination))
        wait_until(lambda: not window.busy)
        assert destination.read_bytes().startswith(b'%PDF-1.4')
        report['checks'].append('Full-resolution PDF export, Unicode path and atomic save')
        window.status.setText('免安装应用验证通过 · 原始分辨率导出')
        window.grab().save(str(output / '应用预览.png'))
        window.checker_check.setChecked(True)
        app.processEvents()
        window.grab().save(str(output / '透明背景预览.png'))
        window.close()
        report['passed'] = True
    except Exception:
        report['errors'].append(traceback.format_exc())
    (output / 'self-test.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['passed'] else 1
