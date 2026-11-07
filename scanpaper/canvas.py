from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QPixmap, QTransform
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView, QLabel


def pixmap_from_pil(image):
    rgba = image.convert('RGBA')
    raw = rgba.tobytes()
    qimage = QImage(raw, rgba.width, rgba.height, rgba.width * 4,
                    QImage.Format.Format_RGBA8888).copy()
    return QPixmap.fromImage(qimage)


class PaperView(QGraphicsView):
    layoutChanged = Signal()
    zoomChanged = Signal(float)

    def __init__(self, layout, parent=None):
        super().__init__(parent)
        self.layout = layout
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setBackgroundBrush(QColor('#e9edf2'))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.paper = QGraphicsRectItem()
        self.paper.setPen(QPen(QColor('#b8c3d1'), 0))
        self.paper.setBrush(Qt.GlobalColor.white)
        self.paper.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape)
        self.scene().addItem(self.paper)
        self.image = self.scene().addPixmap(QPixmap())
        self.image.setParentItem(self.paper)
        self.frame = self.scene().addRect(QRectF(), QPen(QColor('#2563eb'), 0, Qt.PenStyle.DashLine))
        self.handles = []
        for _ in range(4):
            handle = self.scene().addRect(QRectF(-4, -4, 8, 8), QPen(QColor('#2563eb'), 1),
                                          QBrush(Qt.GlobalColor.white))
            handle.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            self.handles.append(handle)
        self.has_image = False
        self.drag = None
        self.fitted = True
        hint_label = QLabel('导入一张扫描件\n\n拖放 JPG 到窗口，或点击「导入图片」')
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_label.setStyleSheet('color:#64748b; background:transparent; font-size:15px;')
        self.hint = self.scene().addWidget(hint_label)
        self.hint.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.hint.setAcceptDrops(False)
        self.hint.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        # Keep the label's center on its scene position at every zoom level.
        center = self.hint.boundingRect().center()
        self.hint.setTransform(QTransform.fromTranslate(-center.x(), -center.y()))
        self.update_layout()

    def update_layout(self):
        pw, ph = self.layout.paper_size
        self.paper.setRect(0, 0, pw, ph)
        self.hint.setPos(self.paper.rect().center())
        self.setSceneRect(QRectF(-30, -30, pw + 60, ph + 60))
        r = QRectF(self.layout.x, self.layout.y, self.layout.width, self.layout.height)
        self.image.setPos(r.topLeft())
        pixmap = self.image.pixmap()
        if not pixmap.isNull():
            self.image.setTransform(QTransform.fromScale(r.width() / pixmap.width(), r.height() / pixmap.height()))
        self.frame.setRect(r)
        for handle, point in zip(self.handles, (r.topLeft(), r.topRight(), r.bottomRight(), r.bottomLeft())):
            handle.setPos(point)
            handle.setVisible(self.has_image)
        self.frame.setVisible(self.has_image)
        self.hint.setVisible(not self.has_image)
        self.viewport().update()

    def set_image(self, image):
        self.image.setPixmap(pixmap_from_pil(image))
        self.has_image = True
        self.update_layout()

    def set_checker(self, enabled):
        if enabled:
            tile = QPixmap(16, 16)
            tile.fill(QColor('#ffffff'))
            painter = QPainter(tile)
            painter.fillRect(0, 0, 8, 8, QColor('#e2e8f0'))
            painter.fillRect(8, 8, 8, 8, QColor('#e2e8f0'))
            painter.end()
            brush = QBrush(tile)
            brush.setTransform(QTransform.fromScale(0.3, 0.3))
            self.paper.setBrush(brush)
        else:
            self.paper.setBrush(Qt.GlobalColor.white)

    def fit_paper(self):
        self.fitted = True
        self.fitInView(self.paper.rect().adjusted(-12, -12, 12, 12), Qt.AspectRatioMode.KeepAspectRatio)
        self.zoomChanged.emit(self.transform().m11())

    def zoom(self, factor):
        current = self.transform().m11()
        target = max(0.15, min(30.0, current * factor))
        self.scale(target / current, target / current)
        self.fitted = False
        self.zoomChanged.emit(target)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fitted:
            self.fit_paper()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom(1.15 if event.angleDelta().y() > 0 else 1 / 1.15)
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.has_image:
            point = self.mapToScene(event.position().toPoint())
            l = self.layout
            corners = [QPointF(l.x, l.y), QPointF(l.x + l.width, l.y),
                       QPointF(l.x + l.width, l.y + l.height), QPointF(l.x, l.y + l.height)]
            for index, corner in enumerate(corners):
                screen = self.mapFromScene(corner)
                delta = event.position() - screen.toPointF()
                if abs(delta.x()) <= 10 and abs(delta.y()) <= 10:
                    self.drag = ('resize', index, corners[(index + 2) % 4], l.width / l.height)
                    event.accept()
                    return
            if QRectF(l.x, l.y, l.width, l.height).contains(point):
                self.drag = ('move', point, l.x, l.y)
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag:
            point = self.mapToScene(event.position().toPoint())
            l = self.layout
            if self.drag[0] == 'move':
                _, start, x, y = self.drag
                l.x = max(-10000, min(10000, x + point.x() - start.x()))
                l.y = max(-10000, min(10000, y + point.y() - start.y()))
            else:
                _, index, anchor, aspect = self.drag
                sx = -1 if index in (0, 3) else 1
                sy = -1 if index in (0, 1) else 1
                dx, dy = (point.x() - anchor.x()) * sx, (point.y() - anchor.y()) * sy
                width = max(0.1, min(10000, (dx + dy / aspect) / (1 + 1 / aspect ** 2)))
                height = width / aspect
                if height > 10000:
                    height, width = 10000, 10000 * aspect
                l.width, l.height = width, height
                l.x = anchor.x() if sx > 0 else anchor.x() - width
                l.y = anchor.y() if sy > 0 else anchor.y() - height
            self.update_layout()
            self.layoutChanged.emit()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag = None
        self.unsetCursor()
        super().mouseReleaseEvent(event)
