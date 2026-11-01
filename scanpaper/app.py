from dataclasses import replace
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QSlider, QVBoxLayout, QWidget)

from .canvas import PaperView
from .model import Layout, PAPERS
from .pdf import export_pdf
from .processing import Cleanup, clean_image, load_jpeg, rotate_image, thumbnail


class JobSignals(QObject):
    done = Signal(object)
    failed = Signal(object)


class Job(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = JobSignals()

    def run(self):
        try:
            result = self.function()
        except Exception as error:
            self.signals.failed.emit(error)
        else:
            self.signals.done.emit(result)


def explain_error(error):
    if isinstance(error, MemoryError):
        return '内存不足，请关闭其他程序，或缩小扫描图片后重试。'
    if isinstance(error, PermissionError):
        return '无法写入文件。请关闭正在使用该 PDF 的程序，并选择有写入权限的文件夹。'
    if isinstance(error, FileNotFoundError):
        return '找不到文件或文件夹，请重新选择。'
    return f'无法完成操作：{error}\n\n请确认图片完整、保存位置可用后重试。'


def section(title):
    box = QGroupBox(title)
    box.setLayout(QVBoxLayout())
    box.layout().setSpacing(12)
    return box


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('净页 ScanPaper · 扫描件转 PDF')
        assets = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / 'assets'
        self.setWindowIcon(QIcon(str(assets / 'scanpaper.svg')))
        self.resize(1280, 860)
        self.setMinimumSize(1040, 700)
        self.setAcceptDrops(True)
        self.layout_model = Layout()
        self.source = None
        self.source_preview = None
        self.processed_preview = None
        self.source_path = None
        self.preview_generation = 0
        self.preview_running = False
        self.preview_pending = False
        self.busy = False
        self.active_jobs = set()
        self.io_pool = QThreadPool(self)
        self.io_pool.setMaxThreadCount(1)
        self.preview_pool = QThreadPool(self)
        self.preview_pool.setMaxThreadCount(1)
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(180)
        self.debounce.timeout.connect(self.start_preview)
        self.build_ui()
        self.sync_layout()
        QTimer.singleShot(0, self.view.fit_paper)

    def build_ui(self):
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(20, 16, 20, 12)
        outer.setSpacing(16)
        top = QHBoxLayout()
        brand = QLabel('净页  <span style="font-size:14px;color:#64748b">ScanPaper</span>')
        brand.setStyleSheet('font-size:25px;font-weight:700;color:#0f172a;')
        top.addWidget(brand)
        subtitle = QLabel('扫描清理  /  纸张排版  /  PDF 导出')
        subtitle.setStyleSheet('color:#64748b;')
        top.addWidget(subtitle)
        top.addStretch()
        self.import_button = QPushButton('导入图片  Ctrl+O')
        self.import_button.clicked.connect(self.choose_image)
        self.export_button = QPushButton('导出 PDF  Ctrl+S')
        self.export_button.setObjectName('primary')
        self.export_button.clicked.connect(self.choose_export)
        self.export_button.setEnabled(False)
        top.addWidget(self.import_button)
        top.addWidget(self.export_button)
        outer.addLayout(top)
        content = QHBoxLayout()
        content.setSpacing(16)
        self.left = QWidget()
        self.left.setFixedWidth(232)
        left = QVBoxLayout(self.left)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(14)
        file_box = section('01  扫描图片')
        self.file_label = QLabel('尚未导入图片')
        self.file_label.setWordWrap(True)
        self.file_label.setTextFormat(Qt.TextFormat.PlainText)
        self.image_info = QLabel('支持 JPG / JPEG\n本地处理 · 无需联网')
        self.image_info.setObjectName('muted')
        file_box.layout().addWidget(self.file_label)
        file_box.layout().addWidget(self.image_info)
        left.addWidget(file_box)
        cleanup_box = section('02  清理背景')
        self.background_slider = self.add_slider(cleanup_box, '背景清理', 35)
        self.ink_slider = self.add_slider(cleanup_box, '笔画增强', 45)
        note = QLabel('优先保留细字与标点。浅色污迹和笔画可能相近，请结合原图调整。')
        note.setWordWrap(True)
        note.setObjectName('muted')
        cleanup_box.layout().addWidget(note)
        self.original_check = QCheckBox('查看原图（仅预览）')
        self.checker_check = QCheckBox('显示透明棋盘格（仅预览）')
        self.original_check.toggled.connect(self.display_preview)
        self.checker_check.toggled.connect(self.view_checker)
        cleanup_box.layout().addWidget(self.original_check)
        cleanup_box.layout().addWidget(self.checker_check)
        left.addWidget(cleanup_box)
        paper_box = section('03  纸张设置')
        self.paper_combo = QComboBox()
        for name, (w, h) in PAPERS.items():
            self.paper_combo.addItem(f'{name}   {w:g} × {h:g} mm', name)
        self.paper_combo.setCurrentIndex(3)
        self.orientation_combo = QComboBox()
        self.orientation_combo.addItems(['纵向', '横向'])
        self.paper_combo.currentIndexChanged.connect(self.change_paper)
        self.orientation_combo.currentIndexChanged.connect(self.change_paper)
        paper_box.layout().addWidget(self.paper_combo)
        paper_box.layout().addWidget(self.orientation_combo)
        left.addWidget(paper_box)
        left.addStretch()
        local = QLabel('文件保留在你的电脑上\n图片不会上传到任何服务器')
        local.setObjectName('muted')
        left.addWidget(local)
        content.addWidget(self.left)
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(8)
        preview_bar = QHBoxLayout()
        preview_bar.addWidget(QLabel('纸张预览'))
        preview_bar.addStretch()
        for title, action in [('−', lambda: self.view.zoom(1 / 1.2)),
                              ('适合窗口', lambda: self.view.fit_paper()),
                              ('＋', lambda: self.view.zoom(1.2))]:
            button = QPushButton(title)
            button.setToolTip('仅调整查看比例，不改变输出尺寸')
            button.clicked.connect(action)
            preview_bar.addWidget(button)
        center_layout.addLayout(preview_bar)
        self.view = PaperView(self.layout_model)
        self.view.layoutChanged.connect(self.sync_layout)
        center_layout.addWidget(self.view, 1)
        self.preview_status = QLabel('拖动图片调整位置 · 拖动四角等比例缩放 · Ctrl+滚轮缩放预览')
        self.preview_status.setObjectName('muted')
        self.preview_status.setWordWrap(True)
        center_layout.addWidget(self.preview_status)
        content.addWidget(center, 1)
        self.right = QWidget()
        self.right.setFixedWidth(220)
        right = QVBoxLayout(self.right)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(14)
        dimensions = section('04  大小与位置')
        form = QFormLayout()
        self.fields = {}
        for key, title in [('width', '宽度'), ('height', '高度'), ('x', '距左'), ('y', '距上')]:
            field = QDoubleSpinBox()
            field.setDecimals(2)
            field.setRange(0.1 if key in ('width', 'height') else -10000, 10000)
            field.setSuffix(' mm')
            field.setKeyboardTracking(False)
            field.setSingleStep(1)
            field.valueChanged.connect(lambda value, name=key: self.change_dimension(name, value))
            form.addRow(title, field)
            self.fields[key] = field
        dimensions.layout().addLayout(form)
        ratio_note = QLabel('宽高始终保持原图比例')
        ratio_note.setObjectName('muted')
        dimensions.layout().addWidget(ratio_note)
        right.addWidget(dimensions)
        actions = section('快速排版')
        for title, action in [('适应纸张 · 留边 10 mm', self.fit_image),
                              ('在纸张上居中', self.center_image),
                              ('顺时针旋转 90°', self.rotate),
                              ('重置图片与清理参数', self.reset_image)]:
            button = QPushButton(title)
            button.clicked.connect(action)
            actions.layout().addWidget(button)
        right.addWidget(actions)
        self.overflow_label = QLabel('')
        self.overflow_label.setWordWrap(True)
        self.overflow_label.setStyleSheet('color:#b45309;background:#fff7ed;border-radius:8px;padding:10px;')
        self.overflow_label.hide()
        right.addWidget(self.overflow_label)
        right.addStretch()
        export_note = QLabel('原始分辨率导出\n透明背景 · 单页 PDF\n纸张之外的内容会被裁切')
        export_note.setObjectName('muted')
        right.addWidget(export_note)
        content.addWidget(self.right)
        outer.addLayout(content, 1)
        bottom = QHBoxLayout()
        self.status = QLabel('准备就绪 · 导入一张扫描件开始')
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setObjectName('muted')
        bottom.addWidget(self.status, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setMaximumWidth(130)
        self.progress.setMaximumHeight(5)
        self.progress.hide()
        bottom.addWidget(self.progress)
        outer.addLayout(bottom)
        self.setCentralWidget(root)
        self.setStyleSheet('''
            QMainWindow, QWidget { background:#f7f9fc; color:#1e293b; }
            QGroupBox { background:white; border:1px solid #dfe5ed; border-radius:10px;
                        margin-top:10px; padding:16px 12px 12px; font-weight:600; }
            QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 5px; }
            QGroupBox QLabel, QGroupBox QCheckBox { background:transparent; font-weight:400; }
            QLabel#muted { color:#64748b; font-size:12px; font-weight:400; }
            QPushButton { background:white; border:1px solid #cbd5e1; border-radius:7px;
                          padding:9px 12px; font-weight:500; }
            QPushButton:hover { background:#eff6ff; border-color:#93b4e8; }
            QPushButton:pressed { background:#dbeafe; }
            QPushButton:disabled { color:#94a3b8; border-color:#e2e8f0; background:#f1f5f9; }
            QPushButton#primary { background:#2563eb; color:white; border:1px solid #2563eb; }
            QPushButton#primary:hover { background:#1d4ed8; }
            QPushButton#primary:disabled { background:#a8bce2; border-color:#a8bce2; }
            QDoubleSpinBox, QComboBox { background:white; border:1px solid #cbd5e1;
                                     border-radius:5px; padding:6px 4px; min-height:20px; }
            QDoubleSpinBox:focus, QComboBox:focus { border-color:#2563eb; }
            QSlider::groove:horizontal { height:5px; background:#dbe3ee; border-radius:2px; }
            QSlider::sub-page:horizontal { background:#2563eb; border-radius:2px; }
            QSlider::handle:horizontal { background:#2563eb; width:14px; margin:-5px 0; border-radius:7px; }
            QCheckBox { spacing:6px; }
            QProgressBar { background:#dbeafe; border:0; }
            QProgressBar::chunk { background:#2563eb; }
        ''')
        self.right.setEnabled(False)
        for sequence, callback in [('Ctrl+O', self.choose_image), ('Ctrl+S', self.choose_export)]:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)

    def add_slider(self, box, title, initial):
        row = QHBoxLayout()
        label = QLabel(title)
        value_label = QLabel(str(initial))
        value_label.setObjectName('muted')
        row.addWidget(label)
        row.addStretch()
        row.addWidget(value_label)
        box.layout().addLayout(row)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(initial)
        slider.valueChanged.connect(lambda value: value_label.setText(str(value)))
        slider.valueChanged.connect(self.queue_preview)
        box.layout().addWidget(slider)
        return slider

    def run_job(self, pool, job, done, failed):
        # Keep signal objects alive until queued delivery on the GUI thread.
        self.active_jobs.add(job)
        def finish(callback, result):
            try:
                callback(result)
            finally:
                self.active_jobs.discard(job)
                job.signals.done.disconnect()
                job.signals.failed.disconnect()
        job.signals.done.connect(lambda result: finish(done, result), Qt.ConnectionType.QueuedConnection)
        job.signals.failed.connect(lambda error: finish(failed, error), Qt.ConnectionType.QueuedConnection)
        pool.start(job)

    def settings(self):
        return Cleanup(self.background_slider.value(), self.ink_slider.value())

    def set_busy(self, busy, message):
        self.busy = busy
        self.import_button.setEnabled(not busy)
        self.export_button.setEnabled(not busy and self.source is not None)
        self.left.setEnabled(not busy)
        self.right.setEnabled(not busy and self.source is not None)
        self.view.setEnabled(not busy)
        self.progress.setVisible(busy)
        self.status.setText(message)

    def choose_image(self):
        if self.busy:
            return
        path, _ = QFileDialog.getOpenFileName(self, '导入扫描件', '', 'JPEG 图片 (*.jpg *.jpeg *.JPG *.JPEG)')
        if path:
            self.load_image(path)

    def load_image(self, path):
        if self.busy:
            return
        if Path(path).suffix.lower() not in ('.jpg', '.jpeg'):
            QMessageBox.information(self, '图片格式', '请导入 JPG 或 JPEG 图片。')
            return
        self.preview_generation += 1
        self.debounce.stop()
        self.preview_pending = False
        self.set_busy(True, '正在读取扫描图片…')
        job = Job(lambda: self.read_source(path))
        self.run_job(self.io_pool, job, lambda result: self.loaded(path, result), self.operation_failed)

    @staticmethod
    def read_source(path):
        source = load_jpeg(path)
        return source, thumbnail(source)

    def loaded(self, path, result):
        self.source, self.source_preview = result
        self.source_path = Path(path)
        self.processed_preview = None
        self.layout_model.rotation = 0
        self.layout_model.fit(self.source.width / self.source.height)
        self.file_label.setText(self.source_path.name)
        self.file_label.setToolTip(str(self.source_path))
        self.image_info.setText(f'{self.source.width:,} × {self.source.height:,} 像素\n原始分辨率保留')
        self.set_busy(False, '图片已导入，正在清理背景…')
        self.view.set_image(self.source_preview)
        self.sync_layout()
        self.view.fit_paper()
        self.queue_preview()

    def queue_preview(self, *_):
        if self.source_preview is None:
            return
        self.preview_generation += 1
        self.status.setText('正在更新清理预览…')
        self.debounce.start()

    def start_preview(self):
        if self.preview_running:
            self.preview_pending = True
            return
        self.preview_running = True
        self.preview_pending = False
        generation = self.preview_generation
        preview, settings = self.source_preview, self.settings()
        job = Job(lambda: (generation, clean_image(preview, settings)))
        self.run_job(self.preview_pool, job, self.finish_preview,
                     lambda error: self.finish_preview_error(generation, error))

    def finish_preview(self, result):
        self.preview_running = False
        self.preview_ready(result)
        if self.preview_pending and not self.debounce.isActive():
            self.start_preview()

    def finish_preview_error(self, generation, error):
        self.preview_running = False
        self.preview_failed(generation, error)
        if self.preview_pending and not self.debounce.isActive():
            self.start_preview()

    def preview_ready(self, result):
        generation, image = result
        if generation != self.preview_generation:
            return
        self.processed_preview = image
        self.display_preview()
        if not self.busy:
            self.status.setText('预览已更新 · 导出始终使用原始分辨率和当前清理参数')

    def preview_failed(self, generation, error):
        if generation == self.preview_generation and not self.busy:
            self.status.setText('预览处理失败，请调整参数或重新导入')
            QMessageBox.warning(self, '处理失败', explain_error(error))

    def display_preview(self, *_):
        if self.source_preview is None:
            return
        image = self.source_preview if self.original_check.isChecked() else self.processed_preview
        if image is not None:
            self.view.set_image(rotate_image(image, self.layout_model.rotation))
        self.preview_status.setText(
            ('当前显示原图；导出仍使用清理结果。' if self.original_check.isChecked() else '') +
            '拖动图片调整位置 · 拖动四角缩放 · Ctrl+滚轮缩放预览')

    def view_checker(self, enabled):
        self.view.set_checker(enabled)

    def sync_layout(self):
        for key, field in self.fields.items():
            field.blockSignals(True)
            field.setValue(getattr(self.layout_model, key))
            field.blockSignals(False)
        self.view.update_layout()
        overflow = self.source is not None and self.layout_model.overflowing
        self.overflow_label.setVisible(overflow)
        self.overflow_label.setText('图片超出纸张范围。导出时，纸张之外的部分会被裁切。')

    def change_dimension(self, key, value):
        if self.source is None:
            return
        l = self.layout_model
        aspect = l.width / l.height
        if key == 'width':
            l.width = min(value, 10000 * aspect)
            l.height = l.width / aspect
        elif key == 'height':
            l.height = min(value, 10000 / aspect)
            l.width = l.height * aspect
        else:
            setattr(l, key, value)
        self.sync_layout()

    def change_paper(self, *_):
        self.layout_model.paper = self.paper_combo.currentData()
        self.layout_model.landscape = self.orientation_combo.currentIndex() == 1
        self.sync_layout()
        self.view.fit_paper()

    def fit_image(self):
        if self.source is None:
            return
        aspect = self.source.width / self.source.height
        if self.layout_model.rotation % 2:
            aspect = 1 / aspect
        self.layout_model.fit(aspect)
        self.sync_layout()

    def center_image(self):
        if self.source is not None:
            self.layout_model.center()
            self.sync_layout()

    def rotate(self):
        if self.source is None:
            return
        l = self.layout_model
        cx, cy = l.x + l.width / 2, l.y + l.height / 2
        l.rotation = (l.rotation + 1) % 4
        l.width, l.height = l.height, l.width
        l.x, l.y = cx - l.width / 2, cy - l.height / 2
        self.display_preview()
        self.sync_layout()

    def reset_image(self):
        if self.source is not None:
            self.layout_model.rotation = 0
            self.background_slider.setValue(35)
            self.ink_slider.setValue(45)
            self.original_check.setChecked(False)
            self.fit_image()
            self.display_preview()
            self.queue_preview()

    def choose_export(self):
        if self.busy or self.source is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, '导出清理后的 PDF',
            str(self.source_path.with_name(self.source_path.stem + '_清理.pdf')), 'PDF 文件 (*.pdf)')
        if not path:
            return
        if Path(path).suffix.lower() != '.pdf':
            path += '.pdf'
            if Path(path).exists() and QMessageBox.question(self, '确认覆盖',
                '此 PDF 已存在，是否覆盖？', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
        self.begin_export(path)

    def begin_export(self, path):
        if self.busy or self.source is None:
            return
        source, settings, layout = self.source, self.settings(), replace(self.layout_model)
        self.set_busy(True, '正在以原始分辨率清理并生成 PDF，请稍候…')
        def write():
            cleaned = rotate_image(clean_image(source, settings), layout.rotation)
            export_pdf(cleaned, layout, path)
            return str(path)
        job = Job(write)
        self.run_job(self.io_pool, job, self.export_ready, self.operation_failed)

    def export_ready(self, path):
        self.set_busy(False, f'已导出：{path}')
        QMessageBox.information(self, '导出完成', f'PDF 已保存到：\n{path}')

    def operation_failed(self, error):
        self.set_busy(False, '操作未完成，可调整后重试')
        QMessageBox.warning(self, '操作失败', explain_error(error))

    def dragEnterEvent(self, event):
        if not self.busy and event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].isLocalFile() and Path(urls[0].toLocalFile()).suffix.lower() in ('.jpg', '.jpeg'):
                event.acceptProposedAction()

    def dropEvent(self, event):
        if not self.busy and event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].isLocalFile():
                self.load_image(urls[0].toLocalFile())
                event.acceptProposedAction()

    def closeEvent(self, event):
        if self.busy:
            QMessageBox.information(self, '正在处理', '正在读取或导出文件，请完成后再关闭窗口。')
            event.ignore()
            return
        self.debounce.stop()
        self.preview_generation += 1
        self.preview_pool.waitForDone()
        super().closeEvent(event)


def configure_font(app):
    app.setStyle('Fusion')
    # The offscreen Qt platform does not discover Windows fonts automatically.
    if app.platformName() == 'offscreen':
        import os
        font_path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'msyh.ttc'
        if font_path.exists():
            QFontDatabase.addApplicationFont(str(font_path))
    app.setFont(QFont('Microsoft YaHei UI', 9))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('ScanPaper')
    app.setOrganizationName('ScanPaper')
    configure_font(app)
    window = MainWindow()
    window.show()
    def report_exception(kind, error, traceback):
        QMessageBox.critical(window, '程序错误', explain_error(error))
    sys.excepthook = report_exception
    return app.exec()
