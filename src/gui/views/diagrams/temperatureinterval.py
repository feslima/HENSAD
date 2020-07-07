import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QFontMetrics, QPen, QResizeEvent, QShowEvent
from PyQt5.QtWidgets import (QApplication, QDialog, QGraphicsScene,
                             QGraphicsView)

from gui.models.core import Setup, StreamFrameMapper, SummaryFrameMapper
from gui.views.common import ArrowItem
from gui.views.py.tempdiagram import Ui_Dialog
from hensad import calculate_intervals, calculate_summary_table

STFM = StreamFrameMapper
SFM = SummaryFrameMapper


class TemperatureIntervalDiagramDialog(QDialog):

    def __init__(self, setup: Setup):
        # ---------------------------- settings -------------------------------
        super().__init__()
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowFlags(Qt.Window)

        view = self.ui.graphicsView
        scene = TemperatureIntervalDiagramScene(setup, view)
        view.setScene(scene)
        self.grScene = scene

        self._setup = setup

        self.ui.approachTempHorizontalSlider.valueChanged.connect(
            self.on_dt_changed
        )

    def on_dt_changed(self, dt_value: int):
        self._setup.dt = float(dt_value)

    def showEvent(self, event: QShowEvent):
        scene = self.grScene
        view = self.ui.graphicsView

        width = view.viewport().width()
        height = view.viewport().height()

        scene.setSceneRect(0, 0, width, height)
        view.fitInView(scene.sceneRect(), Qt.IgnoreAspectRatio)

        return super().showEvent(event)

    def resizeEvent(self, event: QResizeEvent):
        # handle the graph resizing
        view = self.ui.graphicsView
        scene = self.grScene

        view.fitInView(scene.sceneRect(), Qt.IgnoreAspectRatio)
        return super().resizeEvent(event)


class TemperatureIntervalDiagramScene(QGraphicsScene):
    def __init__(self, setup: Setup, parent: QGraphicsView, x: float = 0.0,
                 y: float = 0.0, width: float = 1024.0, height: float = 800):
        super().__init__(x, y, width, height, parent=parent)
        # ----------------------------- settings ------------------------------
        # padding for drawing area
        self._left_p = 75
        self._right_p = 75
        self._top_p = 75
        self._bot_p = 75

        # spacing between left and right sides of the diagram
        self._axis_width = 50

        # ------------------------ internal variables -------------------------
        self._setup = setup
        self._hot_strm_arrows = pd.Series()  # cataloguer of hot side arrows
        self._cold_strm_arrows = pd.Series()  # cataloguer of cold side arrows

        # ------------------------------ signals ------------------------------
        setup.dt_changed.connect(self.update_interval)

        # initialization
        self.update_interval()

    def _map_x(self, x: float) -> float:
        # maps the x coordinates taking into account the padding offset
        return self._left_p + x

    def _map_y(self, y: float) -> float:
        # translate y downward axis into upward
        return self.height() - (self._bot_p + y)

    def _temp_to_px(self, t: float, interval: np.ndarray) -> float:
        # translate temperature values into scene pixels
        scene = self
        h = scene.height() - (self._top_p + self._bot_p)

        # n = np.nonzero(t == interval)[0].item()
        n = np.nonzero(np.isclose(t, interval))[0].item()
        px = n * (h / (interval.size - 1))

        return px

    def _paint_interval_lines(self) -> None:
        scene = self
        w = scene.width() - (self._left_p + self._right_p)
        h = scene.height() - (self._top_p + self._bot_p)

        # label font
        font = QFont()
        font.setBold(True)

        hot_int = self._setup.hot_interval
        dt = self._setup.dt
        int_size = h / (hot_int.size - 1)

        # ------------------------------ DT value -----------------------------
        text = scene.addText("DT = " + str(int(dt)) + "(°C)")
        text.setFont(font)
        fm = QFontMetrics(text.font())
        label_offset = fm.horizontalAdvance(text.toPlainText())
        text.setPos(self._map_x((w - label_offset) / 2), 0.0)

        # ---------------------------- middle axis ----------------------------
        tip_size = 20
        x1 = self._map_x(w / 2 - self._axis_width / 2)
        y1 = self._map_y(-tip_size)
        x2 = x1
        y2 = self._map_y(h + tip_size)

        scene.addLine(x1, y1, x2, y2)

        x1 = self._map_x(w / 2 + self._axis_width / 2)
        y1 = self._map_y(-tip_size)
        x2 = x1
        y2 = self._map_y(h + tip_size)

        scene.addLine(x1, y1, x2, y2)

        # ------------------------- horizontal lines --------------------------
        for i, temp in enumerate(np.flip(hot_int)):
            x_temp = self._map_x(0.0)
            y_temp = self._map_y(self._temp_to_px(temp, np.flip(hot_int)))

            # add the hot side temperature labels
            text = scene.addText("{0:4d} (°C)".format(int(temp)))
            text.setDefaultTextColor(Qt.red)
            text.setFont(font)
            fm = QFontMetrics(text.font())  # measure the text width required
            label_offset = fm.horizontalAdvance(text.toPlainText())
            text.setPos(x_temp - label_offset, y_temp)

            # cold side labels
            text = scene.addText("{0:4d} (°C)".format(int(temp - dt)))
            text.setDefaultTextColor(Qt.blue)
            text.setFont(font)
            text.setPos(x_temp + w/2 + self._axis_width/2, y_temp)

            # horizontal interval lines
            dash_pen = QPen(Qt.DashLine)
            dash_pen.setDashPattern([20, 10])
            line = scene.addLine(0, 0, w, 0, pen=dash_pen)
            line.setPos(x_temp, y_temp)

        # -------------------------- interval labels --------------------------
        summary = self._setup.summary
        for i, temp in enumerate(hot_int[:-1]):
            x = self._map_x(w / 2)
            y = self._map_y(self._temp_to_px(temp, np.flip(hot_int)))
            text = scene.addText(summary.loc[i, SFM.INTERVAL.name])
            text.setFont(font)
            text_size = fm.horizontalAdvance(text.toPlainText())
            text.setPos(x - text_size / 2, y + 0.5 * int_size)

            # Excess heat values
            text = scene.addText("{0:g}".format(
                summary.loc[i, SFM.EXHEAT.name]
            ))
            text.setFont(font)
            text_size = fm.horizontalAdvance(text.toPlainText())
            text.setPos(self._map_x(w), y + 0.5 * int_size)

    def _paint_arrows(self, stream_type: str) -> None:
        scene = self
        w = scene.width() - (self._left_p + self._right_p)
        h = scene.height() - (self._top_p + self._bot_p)

        if stream_type == 'hot':
            t_in = self._setup.hot[STFM.TIN.name]
            t_out = self._setup.hot[STFM.TOUT.name]
            t_int = np.flip(self._setup.hot_interval)
            axis_x_offset = 0
            color = Qt.red
            cataloguer = self._hot_strm_arrows
        elif stream_type == 'cold':
            t_in = self._setup.cold[STFM.TIN.name]
            t_out = self._setup.cold[STFM.TOUT.name]
            t_int = np.flip(self._setup.hot_interval - self._setup.dt)
            axis_x_offset = (w + self._axis_width) / 2
            color = Qt.blue
            cataloguer = self._cold_strm_arrows

        arrow_spacing = (w - self._axis_width) / (2 * (t_in.size + 1))

        for i in range(t_in.size):
            x_shaft = (i + 1) * arrow_spacing + axis_x_offset

            # starting point of arrow shaft
            x1 = self._map_x(x_shaft)
            y1 = self._map_y(self._temp_to_px(t_in[i], t_int))

            # end point of shaft
            x2 = x1
            y2 = self._map_y(self._temp_to_px(t_out[i], t_int))

            arrow = ArrowItem(x1, y1, x2, y2, color=color)
            cataloguer.at[i] = arrow  # store for later referencing
            scene.addItem(arrow)

    def update_interval(self) -> None:
        scene = self

        # clear all items
        self._hot_strm_arrows = pd.Series()
        self._cold_strm_arrows = pd.Series()
        scene.clear()

        self._paint_interval_lines()
        self._paint_arrows('hot')
        self._paint_arrows('cold')


if __name__ == "__main__":
    import sys
    import pathlib

    hsd_filepath = pathlib.Path().resolve() / "tests" / "hsdtest.hsd"

    setup = Setup()
    setup.load(str(hsd_filepath))

    app = QApplication(sys.argv)

    w = TemperatureIntervalDiagramDialog(setup)
    w.show()

    sys.exit(app.exec_())
