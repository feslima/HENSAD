import numpy as np
from PyQt5.QtCore import QRectF, QSizeF, Qt
from PyQt5.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import (QGraphicsItem, QGraphicsLineItem,
                             QStyleOptionGraphicsItem, QWidget)


class ArrowItem(QGraphicsLineItem):
    def __init__(self, x1: float, y1: float, x2: float, y2: float,
                 color: QColor = Qt.black, parent: QGraphicsItem = None):
        super().__init__(x1, y1, x2, y2, parent)
        self._tip_size = 10  # pixels
        self._tip_path = QPainterPath()
        width = 2  # pixels
        pen = QPen(color, width, style=Qt.SolidLine,
                   cap=Qt.RoundCap, join=Qt.RoundJoin)
        self.setPen(pen)

    def boundingRect(self) -> QRectF:
        pen = self.pen()
        line = self.line()
        p1 = line.p1()
        p2 = line.p2()

        # rectangle width
        r_wid = (pen.width() + self._tip_size) / 2.0

        b_rec = QRectF(p1, QSizeF(p2.x() - p1.x(), p2.y() - p1.y()))
        return b_rec.normalized().adjusted(-r_wid, -r_wid, r_wid, r_wid)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem,
              widget: QWidget = None) -> None:
        painter.setPen(self.pen().color())
        painter.setBrush(self.pen().color())
        shaft = self.line()
        painter.drawLine(shaft.p1(), shaft.p2())

        # See implementation notes (OneNote): Drawing an arrow head
        x1, y1 = shaft.p1().x(), shaft.p1().y()
        x2, y2 = shaft.p2().x(), shaft.p2().y()

        d = self._tip_size
        L1 = shaft.length()
        L2 = 0.5 * d * np.sqrt(5)
        angle = np.arcsin(0.5 * d / L2)

        dx = shaft.dx()
        dy = shaft.dy()

        sin = np.sin(angle)
        cos = np.cos(angle)

        x3 = x2 - L2 / L1 * (dx * cos + dy * sin)
        y3 = y2 - L2 / L1 * (dy * cos - dx * sin)

        x4 = x2 - L2 / L1 * (dx * cos - dy * sin)
        y4 = y2 - L2 / L1 * (dy * cos + dx * sin)

        self._tip_path.clear()
        self._tip_path.moveTo(shaft.p2())
        self._tip_path.lineTo(x3, y3)
        self._tip_path.lineTo(x4, y4)
        self._tip_path.closeSubpath()

        # turn on antialiasing for the tip and draw it
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawPath(self._tip_path)

    def shape(self) -> QPainterPath:
        path = super().shape()
        path.addPath(self._tip_path)
        return path
