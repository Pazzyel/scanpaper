"""Packaged-app smoke test. Invoked explicitly, never during normal startup."""
import json
import os
from pathlib import Path
import time
import traceback


def make_scan():
    from .platform_support import resource_path
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    width, height = 1800, 2400
    yy, xx = np.mgrid[:height, :width]
    gray = np.clip(246 - 28 * xx / width - 12 * np.sin(yy / height * np.pi), 0, 255).astype('uint8')
    image = Image.fromarray(gray).convert('RGB')
    draw = ImageDraw.Draw(image)
    try:
        regular = ImageFont.truetype(str(resource_path('assets/fonts/NotoSansCJKsc-Regular.otf')), 30)
        small = ImageFont.truetype(str(resource_path('assets/fonts/NotoSansCJKsc-Regular.otf')), 21)
        heading = ImageFont.truetype(str(resource_path('assets/fonts/NotoSansCJKsc-Regular.otf')), 58)
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
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        from .app import MainWindow
        from .platform_support import configure_application
        from .model import PAPERS
        app = QApplication.instance() or QApplication([])
        configure_application(app)
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
        from PySide6.QtGui import QRawFont
        raw_font = QRawFont.fromFont(app.font())
        assert raw_font.supportsCharacter(ord('净')) and raw_font.supportsCharacter(ord('页'))
        report['checks'].append('Bundled Chinese font and platform keyboard shortcuts')
        source = output / '测试扫描件.jpg'
        make_scan().save(source, quality=96)
        window.show()
        app.processEvents()
        window.resize(1040, 700)
        app.processEvents()
        assert window.left.height() >= window.left.minimumSizeHint().height()
        assert window.left_scroll.verticalScrollBar().maximum() > 0
        window.grab().save(str(output / '最小窗口预览.png'))
        window.resize(1280, 860)
        app.processEvents()
        report['checks'].append('Sidebar remains scrollable without squeezing controls at the minimum window size')
        view = window.view
        for paper, orientation in ((0, 0), (1, 0), (2, 0), (3, 0), (0, 0), (3, 0), (3, 1), (3, 0)):
            window.paper_combo.setCurrentIndex(paper)
            window.orientation_combo.setCurrentIndex(orientation)
            app.processEvents()
            viewport_transform = view.viewportTransform()
            paper_center = viewport_transform.map(view.paper.rect().center())
            hint_transform = view.hint.deviceTransform(viewport_transform)
            hint_center = hint_transform.map(view.hint.boundingRect().center())
            assert view.hint.isVisible() and (hint_center - paper_center).manhattanLength() < 1
        report['checks'].append('Empty-paper hint stays centered when switching size and orientation')
        window.load_image(str(source))
        wait_until(lambda: not window.busy and window.processed_preview is not None)
        assert not view.hint.isVisible()
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
        import re
        from PIL import Image, ImageDraw
        from .processing import Cleanup
        second = output / '横向扫描件.jpg'
        with Image.new('RGB', (2400, 1800), 'white') as landscape:
            drawing = ImageDraw.Draw(landscape)
            drawing.rectangle((260, 220, 2140, 1550), outline='black', width=12)
            drawing.text((350, 340), 'Landscape scan', fill='black', font_size=100)
            landscape.save(second, quality=96)
        from PySide6.QtCore import QMimeData, QUrl
        from PySide6.QtGui import QDragEnterEvent, QDropEvent
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(path)) for path in (source, second)])
        drag = QDragEnterEvent(QPoint(400, 300), Qt.DropAction.CopyAction, mime,
                               Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        window.dragEnterEvent(drag)
        assert drag.isAccepted()
        drop = QDropEvent(QPointF(400, 300), Qt.DropAction.CopyAction, mime,
                          Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        window.dropEvent(drop)
        assert drop.isAccepted()
        wait_until(lambda: not window.busy and window.processed_preview is not None)
        assert len(window.documents) == 2 and window.page_list.count() == 2
        window.background_slider.setValue(62)
        window.ink_slider.setValue(73)
        window.fields['width'].setValue(145)
        first_layout = (window.layout_model.width, window.layout_model.height)
        window.page_list.setCurrentRow(1)
        wait_until(lambda: not window.busy and window.document_index == 1 and window.processed_preview is not None)
        window.background_slider.setValue(12)
        window.paper_combo.setCurrentIndex(2)
        window.orientation_combo.setCurrentIndex(1)
        window.fit_image()
        window.move_up.click()
        assert window.document_index == 0 and window.page_list.currentRow() == 0
        assert window.source_path == second and window.settings() == Cleanup(12, 45)
        assert window.documents[0].path == second
        assert window.page_list.item(0).text().startswith('1. 横向')
        window.page_list.setCurrentRow(1)
        wait_until(lambda: not window.busy and window.document_index == 1 and window.processed_preview is not None)
        assert window.settings() == Cleanup(62, 73)
        assert window.layout_model.paper == 'A4'
        assert first_layout == (window.layout_model.width, window.layout_model.height)
        window.move_up.click()
        window.move_down.click()
        assert [document.path for document in window.documents] == [second, source]
        report['checks'].append('Multi-image import, page reordering and independent cleanup and paper settings')
        window.checker_check.setChecked(False)
        window.grab().save(str(output / '多页排序预览.png'))

        destination = output / '多页导出.pdf'
        window.begin_export(destination)
        wait_until(lambda: not window.busy)
        pdf = destination.read_bytes()
        assert pdf.startswith(b'%PDF-1.4')
        boxes = re.findall(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]', pdf)
        assert len(boxes) == 2 and float(boxes[0][0]) > float(boxes[1][0])
        assert float(boxes[0][0]) > float(boxes[0][1]) and float(boxes[1][0]) < float(boxes[1][1])
        report['checks'].append('The standard export button workflow saves one PDF in the displayed page order')

        second.write_bytes(b'broken jpeg')
        expected_errors = []
        window.operation_failed = lambda error: (expected_errors.append(str(error)), window.set_busy(False, '预期的读取失败'))
        window.page_list.setCurrentRow(0)
        wait_until(lambda: not window.busy)
        assert expected_errors and window.document_index == 1 and window.page_list.currentRow() == 1
        assert window.source_path == source and window.settings() == Cleanup(62, 73)
        report['checks'].append('Failed image switch restores selection and retains the previous document')
        expected_errors.clear()
        window.begin_export(destination)
        wait_until(lambda: not window.busy)
        assert expected_errors and '第 1 页（横向扫描件.jpg）' in expected_errors[0]
        assert destination.read_bytes() == pdf
        report['checks'].append('A failed page preserves the previous PDF and reports the page number')
        window.close()
        report['passed'] = True
    except Exception:
        report['errors'].append(traceback.format_exc())
    (output / 'self-test.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['passed'] else 1
