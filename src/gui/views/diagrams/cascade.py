
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import (
    QFont, QFontMetrics, QPainterPath, QPen, QResizeEvent, QShowEvent)
from PyQt5.QtWidgets import (QApplication, QDialog, QGraphicsScene,
                             QGraphicsView)

from gui.models.core import HFM, SFM, STFM, Setup
from gui.views.common import ArrowItem
from gui.views.py.cascadediagram import Ui_Dialog


class CascadeDiagramDialog(QDialog):
    def __init__(self, setup: Setup):
        super().__init__()
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowFlags(Qt.Window)

        view = self.ui.cascadeDiagramGraphicsView
        self.scene = CascadeDiagramScene(setup, view)
        view.setScene(self.scene)

        self._setup = setup
        self.ui.approachTempHorizontalSlider.valueChanged.connect(
            self.on_dt_changed
        )

    def on_dt_changed(self, dt_value: int):
        self._setup.dt = float(dt_value)

    def showEvent(self, event: QShowEvent):
        scene = self.scene
        view = self.ui.cascadeDiagramGraphicsView

        width = view.viewport().width()
        height = view.viewport().height()

        scene.setSceneRect(0, 0, width, height)
        view.fitInView(scene.sceneRect(), Qt.IgnoreAspectRatio)

        return super().showEvent(event)

    def resizeEvent(self, event: QResizeEvent):
        # handle the graph resizing
        view = self.ui.cascadeDiagramGraphicsView
        scene = self.scene

        view.fitInView(scene.sceneRect(), Qt.IgnoreAspectRatio)
        return super().resizeEvent(event)


class CascadeDiagramScene(QGraphicsScene):
    def __init__(self, setup: Setup, parent: QGraphicsView, x: float = 0.0,
                 y: float = 0.0, width: float = 1024.0, height: float = 800):
        super().__init__(x, y, width, height, parent=parent)
        # ----------------------------- settings ------------------------------
        # padding for drawing area
        self._left_p = 75
        self._right_p = 75
        self._top_p = 75
        self._bot_p = 75

        self._block_width = 100  # pixels
        self._heat_unit = setup.units.power
        self._heat_format = "{0:.6g} {1}"  # 0 - number | 1 - unit

        # ------------------------ internal variables -------------------------
        self._setup = setup
        self._blocks_tracker = {}

        # ------------------------------ signals ------------------------------
        setup.dt_changed.connect(self.paint_diagram)

        # initialization
        self.paint_diagram()

    def _map_x(self, x: float) -> float:
        # maps the x coordinates taking into account the padding offset
        return self._left_p + x

    def _map_y(self, y: float) -> float:
        # translate y downward axis into upward
        return self.height() - (self._bot_p + y)

    def _paint_utility_blocks(self):
        scene = self
        w = scene.width() - (self._left_p + self._right_p)
        h = scene.height() - (self._top_p + self._bot_p)

        block_width = self._block_width
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)

        fm = QFontMetrics(font)
        # hot utility
        pen = QPen(Qt.red, 5, Qt.SolidLine, Qt.SquareCap, Qt.RoundJoin)
        path = QPainterPath()
        path.addRoundedRect(0, 0, block_width, h, 10, 10)
        path = scene.addPath(path, pen=pen)
        path.setPos(self._map_x(0), self._map_y(h))

        text = scene.addText("Hot Utility", font=font)
        text.setDefaultTextColor(Qt.red)
        t_wid = fm.horizontalAdvance(text.toPlainText())
        text.setPos(
            self._map_x((block_width - fm.height()) / 2),
            self._map_y((h - t_wid) / 2)
        )
        text.setRotation(-90.0)

        # cold utility
        pen = QPen(Qt.blue, 5, Qt.SolidLine, Qt.SquareCap, Qt.RoundJoin)
        path = QPainterPath()
        path.addRoundedRect(0, 0, block_width, h, 10, 10)
        path = scene.addPath(path, pen=pen)
        path.setPos(self._map_x(w - block_width), self._map_y(h))

        text = scene.addText("Cold Utility", font=font)
        text.setDefaultTextColor(Qt.blue)
        t_wid = fm.horizontalAdvance(text.toPlainText())
        text.setPos(
            self._map_x(w - (block_width + fm.height()) / 2),
            self._map_y((h - t_wid) / 2)
        )
        text.setRotation(-90.0)

    def _paint_interval_blocks(self):
        scene = self
        w = scene.width() - (self._left_p + self._right_p)
        h = scene.height() - (self._top_p + self._bot_p)

        setup = self._setup
        summary = setup.summary
        n_blocks = len(summary)
        max_exheat = summary.loc[:, SFM.EXHEAT.name].abs().max()

        pen = QPen(Qt.black, 3, Qt.SolidLine, Qt.SquareCap, Qt.RoundJoin)

        # assume that block height and spacing between blocks is the same
        block_height = h / (2 * n_blocks - 1)
        block_width = self._block_width

        # measure minimum height for blocks
        block_font = QFont()
        block_font.setPointSize(12)
        fm = QFontMetrics(block_font)

        label_space = 5  # pixel spacing
        int_height = fm.height()
        heat_height = fm.height()
        label_height = int_height + heat_height + label_space
        minimum_block_height = label_height

        # set a minimum acceptable height (just in case)
        if block_height < minimum_block_height:
            block_height = minimum_block_height
            block_spacing = (h - n_blocks * block_height) / (n_blocks - 1)
            block_font.setPointSize(block_font.pointSize() - 2)

        else:
            block_spacing = block_height

        if np.isnan(self._setup.pinch):
            interval_pinch = None
        else:
            pinch_idx = summary.index[
                summary[SFM.TOUT.name] == setup.pinch
            ].values.item()
            interval_pinch = summary.at[pinch_idx, SFM.INTERVAL.name]

        for i in range(n_blocks):
            block = scene.addRect(0, 0, block_width, block_height, pen=pen)
            block_h_s = (block_height + block_spacing) * i
            block.setPos(
                self._map_x((w - block_width) / 2),
                self._map_y(h - block_h_s)
            )

            int_name = summary.at[i, SFM.INTERVAL.name]
            int_exheat = self._heat_format.format(
                summary.at[i, SFM.EXHEAT.name],
                self._heat_unit)

            int_label = scene.addText(int_name, block_font)
            int_ex_heat = scene.addText(int_exheat, block_font)

            int_width = fm.horizontalAdvance(int_label.toPlainText())
            heat_width = fm.horizontalAdvance(int_ex_heat.toPlainText())

            int_label.setPos(
                self._map_x((w - int_width) / 2),
                self._map_y(
                    h - (block_h_s + (block_height - label_height) / 2)
                )
            )
            int_ex_heat.setPos(
                self._map_x((w - heat_width) / 2),
                self._map_y(
                    h - (block_h_s + (block_height) / 2)
                )
            )

            # paint pinch line if there is one
            if interval_pinch is not None and int_name == interval_pinch:
                pinch_pen = QPen()
                pinch_pen.setWidth(3)
                pinch_pen.setDashPattern([10.0, 5.0])
                line = scene.addLine(
                    10, 0, w - 2 * block_width - 10, 0, pinch_pen)
                line.setPos(
                    self._map_x(block_width),
                    self._map_y(h - block_h_s - 1.5 * block_spacing)
                )

                text = scene.addText("Pinch")
                pinch_font = QFont()
                pinch_font.setBold(True)
                pinch_font.setPointSize(10)
                text.setFont(pinch_font)
                t_wid = fm.horizontalAdvance(text.toPlainText())
                text.setPos(
                    self._map_x((w - t_wid) / 2),
                    self._map_y(h - block_h_s - 1.5 * block_spacing)
                )

            self._blocks_tracker[int_name] = block

    def _paint_heat_flow_arrows(self) -> None:
        scene = self
        w = scene.width() - (self._left_p + self._right_p)
        h = scene.height() - (self._top_p + self._bot_p)

        n_blocks = len(self._blocks_tracker)
        int_names = list(self._blocks_tracker.keys())
        int_blocks = list(self._blocks_tracker.values())

        flow_font = QFont()
        flow_font.setPointSize(12)
        fm = QFontMetrics(flow_font)

        idx = 0
        heat_flow = self._setup.heat_flow
        while idx < (n_blocks - 1):
            cur_block = int_blocks[idx]
            nxt_block = int_blocks[idx + 1]

            blk_pen = cur_block.pen()

            if heat_flow.at[idx, HFM.OUT.name] > 0:
                # paint flow between intervals
                b_mid = cur_block.pos().x() + cur_block.rect().size().width() / 2
                b_bot = cur_block.pos().y() + cur_block.rect().size().height()

                b_top = nxt_block.pos().y()

                arrow = ArrowItem(b_mid, b_bot, b_mid, b_top,
                                  color=blk_pen.color(),
                                  width=blk_pen.width())

                scene.addItem(arrow)

                out_flow = heat_flow.at[idx, HFM.OUT.name]
                text = scene.addText(
                    self._heat_format.format(
                        out_flow,
                        self._heat_unit
                    ), font=flow_font
                )
                t_wid = fm.horizontalAdvance(text.toPlainText())
                t_hei = fm.height()
                t_x = cur_block.pos().x() + cur_block.rect().size().width()
                t_y = b_bot + (b_top - b_bot - t_hei) / 2
                text.setPos(t_x, t_y)
            else:
                # paint flow from hot utility
                b_x1 = self._map_x(self._block_width)
                b_x2 = cur_block.pos().x()

                b_y = cur_block.pos().y() + cur_block.rect().size().height() / 2

                arrow = ArrowItem(b_x1, b_y, b_x2, b_y)

                scene.addItem(arrow)

                util_flow = heat_flow.at[idx, HFM.UTIL.name]
                text = scene.addText(
                    self._heat_format.format(
                        util_flow,
                        self._heat_unit
                    ), font=flow_font
                )
                t_wid = fm.horizontalAdvance(text.toPlainText())
                t_hei = fm.height()
                text.setPos((b_x2 - b_x1 - t_wid) / 2 + b_x1, b_y)

            idx += 1

        # check if there is residual heat to be dumped into the cold utility
        last_flow = heat_flow.at[n_blocks - 1, HFM.OUT.name]
        if last_flow > 0:
            cur_block = int_blocks[-1]
            b_x1 = cur_block.pos().x() + cur_block.rect().size().width()
            b_x2 = self._map_x(w - self._block_width)

            b_y = cur_block.pos().y() + cur_block.rect().size().height() / 2

            arrow = ArrowItem(b_x1, b_y, b_x2, b_y)

            scene.addItem(arrow)

            text = scene.addText(
                self._heat_format.format(
                    last_flow,
                    self._heat_unit
                ), font=flow_font)
            t_wid = fm.horizontalAdvance(text.toPlainText())
            t_hei = fm.height()
            text.setPos((b_x2 - b_x1 - t_wid) / 2 + b_x1, b_y)

    def paint_diagram(self) -> None:
        scene = self
        w = scene.width() - (self._left_p + self._right_p)
        h = scene.height() - (self._top_p + self._bot_p)

        scene.clear()
        self._blocks_tracker = {}

        self._paint_utility_blocks()
        self._paint_interval_blocks()
        self._paint_heat_flow_arrows()


if __name__ == "__main__":
    import sys
    import pathlib

    hsd_filepath = pathlib.Path().resolve() / "tests" / "hsdtest.hsd"

    setup = Setup()
    setup.load(str(hsd_filepath))

    app = QApplication(sys.argv)

    w = CascadeDiagramDialog(setup)
    w.show()

    sys.exit(app.exec_())
