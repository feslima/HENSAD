import pathlib

import numpy as np
import pandas as pd
from PyQt5.QtCore import (QAbstractTableModel, QModelIndex, QPointF, QRectF,
                          QRegExp, QSize, QSizeF, Qt, pyqtSignal)
from PyQt5.QtGui import (QColor, QDoubleValidator, QFont, QFontMetrics, QIcon,
                         QIntValidator, QPainter, QPainterPath, QPen, QPixmap,
                         QRegExpValidator, QResizeEvent, QShowEvent,
                         QTransform, QValidator)
from PyQt5.QtWidgets import (QAction, QApplication, QComboBox, QDialog,
                             QDialogButtonBox, QFileDialog, QFormLayout,
                             QGraphicsEllipseItem, QGraphicsItem,
                             QGraphicsLineItem, QGraphicsScene,
                             QGraphicsSceneContextMenuEvent,
                             QGraphicsSceneHoverEvent,
                             QGraphicsSceneMouseEvent, QGraphicsView,
                             QGridLayout, QHeaderView, QLabel, QLineEdit,
                             QMenu, QStyleOptionGraphicsItem, QTableView,
                             QToolBar, QVBoxLayout, QWidget, QMessageBox)

from gui.models.core import (COST_DATA, HEDFM, MATERIAL_DATA, SFM, STFCFM,
                             STFM, ArrangementType, ExchangerType,
                             MaterialType, Setup)
from gui.models.exchanger_table import ExchangerDesignTableModel
from gui.resources import icons_rc
from gui.views.common import ArrowItem

_MAX_NUM_DIGITS = 10


class NamedArrow(ArrowItem):
    def __init__(self, name: str, x1: float, y1: float, x2: float, y2: float,
                 color: QColor = Qt.black, width: int = 2,
                 parent: QGraphicsItem = None):
        self.name = name
        super().__init__(x1, y1, x2, y2, color=color, width=width,
                         parent=parent)

    def _create_menu(self) -> None:
        split_icon = QIcon()
        self._split_action = QAction(
            split_icon, "Split stream", self.scene()
        )
        self._split_action.triggered.connect(self._split_stream)

        util_icon = QIcon()
        self._utility_action = QAction(
            util_icon, "Insert Utility Exchanger", self.scene()
        )
        self._utility_action.triggered.connect(self._add_utility_echanger)

        self.context_menu = QMenu()
        self.context_menu.addAction(self._split_action)
        self.context_menu.addAction(self._utility_action)

    def _split_stream(self) -> None:
        scene = self.scene()
        stream_type = 'hot' if type(self) == LiveArrowItem else 'cold'
        stream_id = self.name
        dialog = SplitStreamDialog(stream_id, stream_type, scene)
        dialog.exec_()

    def _add_utility_echanger(self) -> None:
        # get which design scene and interval the exchanger is to be added
        scene = self.scene()
        des_type = scene._des_type
        interval = np.unique(
            scene._hot_str.loc[
                :,
                [STFCFM.TIN.name, STFCFM.TOUT.name]
            ].values
        )

        source_inter = scene._px_to_interval(
            self._context_ypos_click, interval
        )
        setup = scene._setup
        summary = setup.summary
        pinch = setup.pinch
        if des_type == 'abv':
            summary_indexer = summary[SFM.TOUT.name] >= pinch
        else:
            summary_indexer = summary[SFM.TIN.name] <= pinch

        summary = summary.loc[
            summary_indexer,
            :
        ].reset_index(drop=True)
        inter = summary.at[source_inter, SFM.INTERVAL.name]

        if type(self) == NamedArrow:
            # inject heat from hot utility into cold stream
            source_name = 'Hot utility'
            dest_name = self.name

        elif type(self) == LiveArrowItem:
            # extract heat from hot stream into cold utility
            source_name = self.name
            dest_name = 'Cold utility'

        dialog = ExchangerInputDialog('utility', des_type,
                                      inter,
                                      source_name, dest_name,
                                      setup)
        dialog.exec_()

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        self.scene().clearSelection()
        self.setSelected(True)

        self._context_ypos_click = event.scenePos().y()

        self._create_menu()

        # call the context menu at the item position
        self.context_menu.exec_(event.screenPos())


class LiveArrowItem(NamedArrow):
    def __init__(self, name: str, x1: float, y1: float, x2: float, y2: float,
                 color: QColor = Qt.black, width: int = 2,
                 parent: QGraphicsItem = None):
        super().__init__(name, x1, y1, x2, y2, color=color, width=width,
                         parent=parent)
        self.setAcceptHoverEvents(True)

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent):
        # changes the mouse cursor to a cross when hovering this item
        QApplication.setOverrideCursor(Qt.CrossCursor)
        return super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent):
        QApplication.restoreOverrideCursor()
        return super().hoverLeaveEvent(event)


class ProcessExchangerItem(QGraphicsLineItem):
    def __init__(self, x1: float, y1: float, x2: float, y2: float,
                 label: str, duty: float, des_type: str, setup: Setup,
                 color: QColor = Qt.black, width: int = 2,
                 parent: QGraphicsItem = None):
        super().__init__(x1, y1, x2, y2, parent)
        self._label = label
        self._duty = duty
        self._des_type = des_type
        self._setup = setup

        self._ex_label_radius = 20  # pixels

        pen = QPen(color, width, style=Qt.SolidLine,
                   cap=Qt.RoundCap, join=Qt.RoundJoin)
        self.setPen(pen)

    def _create_action(self) -> None:
        del_icon = QIcon()
        del_icon.addPixmap(
            QPixmap(":/streams/delete_icon.svg"), QIcon.Normal, QIcon.Off
        )
        self._delete_action = QAction(
            del_icon, "Delete exchanger", self.scene()
        )
        self._delete_action.triggered.connect(self._delete_exchanger)

    def _create_context_menu(self) -> None:
        self.context_menu = QMenu()
        self.context_menu.addAction(self._delete_action)

    def _delete_exchanger(self):
        self._setup.delete_exchanger(self._label, self._des_type)

    def boundingRect(self) -> QRectF:
        pen = self.pen()
        line = self.line()
        p1 = line.p1()
        p2 = line.p2()

        # rectangle width
        r_wid = self._ex_label_radius + pen.width()

        b_rec = QRectF(p1, QSizeF(p2.x() - p1.x(), p2.y() - p1.y()))
        return b_rec.normalized().adjusted(-r_wid, -r_wid, r_wid, r_wid)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem,
              widget: QWidget = None) -> None:
        painter.setPen(self.pen())
        shaft = self.line()

        x1 = shaft.x1()
        y1 = shaft.y1()
        x2 = shaft.x2()
        y2 = shaft.y2()

        # draw tips "knobs"
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(self.pen().color())
        k_radius = 5  # pixels
        painter.drawEllipse(QRectF(
            QPointF(x1 - k_radius, y1 - k_radius),
            QPointF(x1 + k_radius, y1 + k_radius)
        ))

        painter.drawEllipse(QRectF(
            QPointF(x2 - k_radius, y2 - k_radius),
            QPointF(x2 + k_radius, y2 + k_radius)
        ))
        painter.setBrush(Qt.NoBrush)
        painter.setRenderHint(QPainter.Antialiasing, False)

        # draw label circle in the middle of the shaft
        radius = self._ex_label_radius
        mid_x = 0.5 * (x1 + x2)
        left_x2 = mid_x - radius
        right_x2 = mid_x + radius

        painter.drawEllipse(QRectF(
            QPointF(left_x2, y1 - radius),
            QPointF(right_x2, y1 + radius)
        ))

        # paint the line
        painter.drawLine(shaft.p1(), QPointF(left_x2, shaft.y1()))
        painter.drawLine(QPointF(right_x2, shaft.y1()), shaft.p2())

        # write the label
        font = QFont()
        font.setBold(True)
        fm = QFontMetrics(font)
        label_text = self._label + '\n{0:.6g}'.format(self._duty)

        # measure the text height and width
        rect = fm.boundingRect(
            QApplication.desktop().geometry(),
            Qt.TextWordWrap | Qt.AlignCenter,
            label_text
        )
        label_width = rect.width()
        label_height = rect.height()

        # draw the text
        painter.setFont(font)
        painter.drawText(
            QRectF(
                mid_x - 0.5 * label_width, y1 - 0.5 * label_height,
                label_width, label_height
            ),
            Qt.AlignCenter,
            label_text,
        )

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        self.scene().clearSelection()
        self.setSelected(True)

        self._create_action()
        self._create_context_menu()

        # call the context menu at the item position
        self.context_menu.exec_(event.screenPos())


class UtilityExchangerItem(QGraphicsEllipseItem):
    def __init__(self, x: float, y: float, label: str, duty: float,
                 des_type: str, setup: Setup, d: float = 40.0,
                 color: QColor = Qt.black, width: int = 2,
                 parent: QGraphicsItem = None):
        # the 'x' and 'y' in this case refers to the center of the circle
        super().__init__(x - 0.5 * d, y - 0.5 * d, d, d, parent=parent)

        self._label = label
        self._duty = duty
        self._des_type = des_type
        self._setup = setup

        self._d = d

        pen = QPen(color, width, style=Qt.SolidLine,
                   cap=Qt.RoundCap, join=Qt.RoundJoin)
        self.setPen(pen)
        self.setBrush(Qt.white)

    def _create_action(self) -> None:
        del_icon = QIcon()
        del_icon.addPixmap(
            QPixmap(":/streams/delete_icon.svg"), QIcon.Normal, QIcon.Off
        )
        self._delete_action = QAction(
            del_icon, "Delete exchanger", self.scene()
        )
        self._delete_action.triggered.connect(self._delete_exchanger)

    def _create_context_menu(self) -> None:
        self.context_menu = QMenu()
        self.context_menu.addAction(self._delete_action)

    def _delete_exchanger(self):
        self._setup.delete_exchanger(self._label, self._des_type)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem,
              widget: QWidget = None) -> None:
        super().paint(painter, option, widget)

        # write the label
        font = QFont()
        font.setBold(True)
        fm = QFontMetrics(font)
        label_text = self._label + '\n{0:.6g}'.format(self._duty)

        # measure the text height and width
        rect = fm.boundingRect(
            QApplication.desktop().geometry(),
            Qt.TextWordWrap | Qt.AlignCenter,
            label_text
        )
        label_width = rect.width()
        label_height = rect.height()

        # draw the text
        x = self.rect().x()
        y = self.rect().y()
        d = self._d

        mid_x = x + d * 0.5
        mid_y = y + d * 0.5

        painter.setFont(font)
        painter.drawText(
            QRectF(
                mid_x - 0.5 * label_width, mid_y - 0.5 * label_height,
                label_width, label_height
            ),
            Qt.AlignCenter,
            label_text,
        )

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        self.scene().clearSelection()
        self.setSelected(True)

        self._create_action()
        self._create_context_menu()

        # call the context menu at the item position
        self.context_menu.exec_(event.screenPos())


class PinchDesignDialog(QDialog):
    def __init__(self, setup: Setup, filename: str):
        super().__init__()
        self.resize(1024, 800)
        self.setMinimumSize(QSize(1024, 800))
        self.setWindowFlags(Qt.Window)

        self._setup = setup
        self._filename = filename

        self.createUi()

    def save_design(self):
        if pathlib.Path(self._filename).resolve().exists():
            self._setup.save(self._filename)
        else:
            self._save_as()

    def _save_as(self):
        dialog_title = "Select the name and where to save the .hsd file"
        filetype = "HENSAD files (*.hsd)"
        homedir = pathlib.Path().home()

        hsd_filepath, _ = QFileDialog.getSaveFileName(
            self,
            dialog_title,
            str(homedir),
            filetype
        )

        if hsd_filepath != '':
            self._filename = str(hsd_filepath)
            self._setup.save(str(hsd_filepath))

    def createUi(self):
        toolbar = QToolBar(self)

        save_icon = QIcon()
        save_icon.addPixmap(
            QPixmap(":/files/save_icon.svg"), QIcon.Normal, QIcon.Off
        )
        save_action = QAction(save_icon, 'Save', self)
        save_action.triggered.connect(self.save_design)

        toolbar.addAction(save_action)

        above_table_view = QTableView(self)
        above_table_model = ExchangerDesignTableModel(
            self._setup, 'abv', above_table_view
        )
        above_table_view.setModel(above_table_model)
        above_table_view.setMinimumHeight(100)
        above_table_view.setMaximumHeight(150)

        largest_header = max(HEDFM.headers(), key=len)
        font = QFont()
        font.setBold(True)
        fm = QFontMetrics(font)
        header = above_table_view.horizontalHeader()
        header.setMinimumSectionSize(fm.horizontalAdvance(largest_header))
        header.setSectionResizeMode(QHeaderView.Stretch)

        below_table_view = QTableView(self)
        below_table_model = ExchangerDesignTableModel(
            self._setup, 'blw', below_table_view
        )
        below_table_view.setModel(below_table_model)
        below_table_view.setMinimumHeight(100)
        below_table_view.setMaximumHeight(150)

        largest_header = max(HEDFM.headers(), key=len)
        fm = QFontMetrics(font)
        header = below_table_view.horizontalHeader()
        header.setMinimumSectionSize(fm.horizontalAdvance(largest_header))
        header.setSectionResizeMode(QHeaderView.Stretch)

        self.above_view = QGraphicsView(self)
        self.above_scene = PinchDesignScene(
            'abv', self._setup, self.above_view)
        self.above_view.setScene(self.above_scene)

        self.below_view = QGraphicsView(self)
        self.below_scene = PinchDesignScene(
            'blw', self._setup, self.below_view)
        self.below_view.setScene(self.below_scene)

        layout = QGridLayout()
        layout.addWidget(toolbar, 0, 0, 1, 1)
        layout.addWidget(above_table_view, 1, 0, 1, 1)
        layout.addWidget(self.above_view, 2, 0, 1, 1)
        layout.addWidget(below_table_view, 1, 1, 1, 1)
        layout.addWidget(self.below_view, 2, 1, 1, 1)
        self.setLayout(layout)

    def showEvent(self, event: QShowEvent):
        self.resize_scene()

        return super().showEvent(event)

    def resizeEvent(self, event: QResizeEvent):
        # handle the graph resizing
        self.resize_scene()
        return super().resizeEvent(event)

    def resize_scene(self):
        above_view = self.above_view
        above_scene = self.above_scene

        width = above_view.viewport().width()
        height = above_view.viewport().height()

        above_scene.setSceneRect(0, 0, width, height)
        above_scene.paint_interval_diagram()
        above_scene.paint_exchangers()

        below_view = self.below_view
        below_scene = self.below_scene

        width = below_view.viewport().width()
        height = below_view.viewport().height()

        below_scene.setSceneRect(0, 0, width, height)
        below_scene.paint_interval_diagram()
        below_scene.paint_exchangers()

        below_view.fitInView(below_scene.sceneRect(), Qt.IgnoreAspectRatio)


class PinchDesignScene(QGraphicsScene):
    def __init__(self, des_type: str, setup: Setup, parent: QGraphicsView):
        super().__init__(0.0, 0.0, 1024.0, 800.0, parent=parent)
        # ----------------------------- settings ------------------------------
        # padding for drawing area
        self._left_p = 100
        self._right_p = 100
        self._top_p = 75
        self._bot_p = 75

        # spacing between left and right sides of the diagram
        self._axis_width = 50

        # ------------------------ internal variables -------------------------
        self._des_type = des_type
        self._setup = setup
        self._hot_strm_arrows = pd.Series()  # cataloguer of hot side arrows
        self._cold_strm_arrows = pd.Series()  # cataloguer of cold side arrows
        self._design_lines = []  # cataloguer of exchangers

        if self._des_type == 'abv':
            self._hot_str = self._setup.hot_above
            self._cold_str = self._setup.cold_above
            self._design = self._setup.design_above
            self._setup.design_above_changed.connect(self.paint_exchangers)
        else:
            self._hot_str = self._setup.hot_below
            self._cold_str = self._setup.cold_below
            self._design = self._setup.design_below
            self._setup.design_below_changed.connect(self.paint_exchangers)

    def paint_interval_diagram(self) -> None:
        scene = self

        # clear all items
        self._hot_strm_arrows = pd.Series()
        self._cold_strm_arrows = pd.Series()
        scene.clear()

        # read stream data
        if self._des_type == 'abv':
            self._hot_str = self._setup.hot_above
            self._cold_str = self._setup.cold_above
        else:
            self._hot_str = self._setup.hot_below
            self._cold_str = self._setup.cold_below

        self._paint_horizontal_lines()
        self._paint_arrows('hot')
        self._paint_arrows('cold')

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

        n = np.nonzero(t == interval)[0].item()
        px = n * (h / (interval.size - 1))

        return px

    def _px_to_interval(self, px: float, interval: np.ndarray) -> int:
        scene = self
        h = scene.height() - (self._top_p + self._bot_p)
        interval_height = h / (interval.size - 1)
        t = np.floor((px - self._top_p) / interval_height)
        return int(t)

    def _paint_horizontal_lines(self) -> None:
        scene = self
        w = scene.width() - (self._left_p + self._right_p)
        h = scene.height() - (self._top_p + self._bot_p)

        # label font
        temp_lbl_fmt = '{0:4g} ({1})'
        font = QFont()
        font.setBold(True)

        hot_int = np.unique(
            self._hot_str.loc[
                :,
                [STFCFM.TIN.name, STFCFM.TOUT.name]
            ].values
        )
        dt = self._setup.dt
        int_size = h / (hot_int.size - 1)

        for i, temp in enumerate(hot_int):
            x_temp = self._map_x(0.0)
            y_temp = self._map_y(self._temp_to_px(temp, hot_int))

            # add the hot side temperature labels
            temp_lbl = temp_lbl_fmt.format(
                temp,
                self._setup.units.temperature
            )
            text = scene.addText(temp_lbl)
            text.setDefaultTextColor(Qt.red)
            text.setFont(font)
            fm = QFontMetrics(text.font())  # measure the text width required
            label_offset = fm.horizontalAdvance(text.toPlainText())
            text.setPos(x_temp - label_offset, y_temp)

            # cold side labels
            temp_lbl = temp_lbl_fmt.format(
                temp - dt,
                self._setup.units.temperature
            )
            text = scene.addText(temp_lbl)
            text.setDefaultTextColor(Qt.blue)
            text.setFont(font)
            text.setPos(x_temp + w, y_temp)

            # horizontal interval lines
            dash_pen = QPen(Qt.DashLine)
            dash_pen.setDashPattern([20, 10])
            line = scene.addLine(0, 0, w, 0, pen=dash_pen)
            line.setPos(x_temp, y_temp)

    def _paint_arrows(self, stream_type: str) -> None:
        scene = self
        w = scene.width() - (self._left_p + self._right_p)
        h = scene.height() - (self._top_p + self._bot_p)

        if stream_type == 'hot':
            t_in = self._hot_str[STFCFM.TIN.name]
            t_out = self._hot_str[STFCFM.TOUT.name]
            t_int = np.unique(
                self._hot_str.loc[
                    :,
                    [STFCFM.TIN.name, STFCFM.TOUT.name]
                ].values
            )
            axis_x_offset = 0
            color = Qt.red
            cataloguer = self._hot_strm_arrows
        elif stream_type == 'cold':
            t_in = self._cold_str[STFCFM.TIN.name]
            t_out = self._cold_str[STFCFM.TOUT.name]
            t_int = np.unique(
                self._hot_str.loc[
                    :,
                    [STFCFM.TIN.name, STFCFM.TOUT.name]
                ].values
            ) - self._setup.dt
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

            if stream_type == 'hot':
                arr_id = self._hot_str.at[i, STFCFM.ID.name]
                arrow = LiveArrowItem(arr_id, x1, y1, x2, y2, color=color)
            else:
                arr_id = self._cold_str.at[i, STFCFM.ID.name]
                arrow = NamedArrow(arr_id, x1, y1, x2, y2, color=color)

            cataloguer.at[arr_id] = arrow  # store for later referencing
            scene.addItem(arrow)

    def paint_exchangers(self) -> None:
        scene = self
        for ex in self._design_lines:
            try:
                scene.removeItem(ex)
            except RuntimeError as ex:
                pass

        self._design_lines = []

        if self._des_type == 'abv':
            design = self._setup.design_above
        else:
            design = self._setup.design_below

        interval = np.unique(
            self._hot_str.loc[
                :,
                [STFCFM.TIN.name, STFCFM.TOUT.name]
            ].values
        )

        h = scene.height() - (self._top_p + self._bot_p)
        interval_height = h / (interval.size - 1)

        labels = design[HEDFM.INT.name]
        summary = self._setup.summary.set_index(SFM.INTERVAL.name)
        for i, inter in enumerate(labels.unique()):
            # paint exchangers by interval
            exchangers = design.loc[inter == labels, :].reset_index(drop=True)
            n_exchangers = len(exchangers)

            if n_exchangers != 0:
                sub_int_height = interval_height / (n_exchangers)

                # for each exchanger in this interval
                for i_ex, ex in exchangers.iterrows():
                    # convert the hot inlet of the interval to pixel offset
                    tin = summary.at[inter, SFM.TIN.name]
                    tin_px = self._map_y(self._temp_to_px(tin, interval))
                    y = (i_ex + 0.5) * sub_int_height + tin_px

                    ex_label = ex[HEDFM.ID.name]
                    ex_duty = ex[HEDFM.DUTY.name]
                    src_strm = ex[HEDFM.SOURCE.name]
                    dst_strm = ex[HEDFM.DEST.name]

                    if src_strm == 'Hot utility' or dst_strm == 'Cold utility':
                        # utility exchanger
                        if src_strm == 'Hot utility':
                            x = self._cold_strm_arrows[dst_strm].line().x1()
                        elif dst_strm == 'Cold utility':
                            x = self._hot_strm_arrows[src_strm].line().x1()

                        ex_item = UtilityExchangerItem(
                            x, y, ex_label, ex_duty,
                            self._des_type, self._setup
                        )

                    else:
                        # process exchanger
                        # determine the line tips
                        source_x = self._hot_strm_arrows[src_strm].line().x1()
                        dest_x = self._cold_strm_arrows[dst_strm].line().x1()

                        # paint the exchanger
                        ex_item = ProcessExchangerItem(
                            source_x, y, dest_x, y,
                            ex_label, ex_duty,
                            self._des_type, self._setup
                        )

                    scene.addItem(ex_item)
                    self._design_lines.append(ex_item)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton:
            trans = self.parent().transform()

            item = self.itemAt(event.scenePos(), trans)
            if isinstance(item, LiveArrowItem):
                self._source_item = item.name
                self._source_y = event.scenePos().y()
                self._accepts_hover = True
            else:
                self._source_item = None
                self._source_y = None
                self._accepts_hover = False

        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton:
            trans = self.parent().transform()

            item = self.itemAt(event.scenePos(), trans)
            if isinstance(item, NamedArrow) and \
                self._source_y is not None and \
                    self._accepts_hover:

                interval = np.unique(
                    self._hot_str.loc[
                        :,
                        [STFCFM.TIN.name, STFCFM.TOUT.name]
                    ].values
                )

                source_inter = self._px_to_interval(self._source_y, interval)
                dest_inter = self._px_to_interval(
                    event.scenePos().y(), interval
                )

                if source_inter == dest_inter:
                    # if the intervals of the clicks are the same, prompt user
                    summary = self._setup.summary
                    pinch = self._setup.pinch
                    if self._des_type == 'abv':
                        summary_indexer = summary[SFM.TOUT.name] >= pinch
                    else:
                        summary_indexer = summary[SFM.TIN.name] <= pinch
                    summary = summary.loc[
                        summary_indexer,
                        :
                    ].reset_index(drop=True)
                    inter = summary.at[source_inter, SFM.INTERVAL.name]
                    dialog = ExchangerInputDialog('process', self._des_type,
                                                  inter,
                                                  self._source_item, item.name,
                                                  self._setup)
                    dialog.exec_()

        return super().mouseReleaseEvent(event)


class ExchangerInputDialog(QDialog):
    def __init__(self, ex_type: str, des_type: str, interval: str, source: str,
                 dest: str, setup: Setup, parent=None):
        super().__init__(parent=parent)
        self._ex_type = ex_type  # whether 'process' or 'utility' exchanger
        self.createUi()

        self._des_type = des_type
        self._interval = interval
        self._source = source
        self._dest = dest
        self._setup = setup

    def createUi(self):
        self.setWindowModality(Qt.ApplicationModal)
        self.setModal(True)
        self.setWindowTitle("Exchanger parameters")
        self.resize(250, 150)

        label1 = QLabel("Exchanger ID:", self)
        label2 = QLabel("Exchanger Duty:", self)
        label3 = QLabel("Correction Factor:", self)
        label4 = QLabel("Exchanger Type:", self)
        label5 = QLabel("Tube Arrangement:", self)
        label6 = QLabel("Shell side material:", self)
        label7 = QLabel("Tube side material:", self)
        label8 = QLabel("Operating pressure:", self)

        reg_ex = QRegExp("^[A-Z$a-z$0-9][a-z_$0-9]{,9}$")
        id_validator = QRegExpValidator(reg_ex)
        duty_validator = QDoubleValidator(0.0, 1.0e9, _MAX_NUM_DIGITS)
        pressure_validator = QDoubleValidator(0.0, 1.0e9, _MAX_NUM_DIGITS)
        factor_validator = QDoubleValidator(0.0, 1.0, 3)

        id_edit = QLineEdit(self)
        id_edit.setAlignment(Qt.AlignCenter)
        id_edit.setValidator(id_validator)
        id_edit.textChanged.connect(self.check_inputs)
        self._id_edit = id_edit

        duty_editor = QLineEdit(self)
        duty_editor.setAlignment(Qt.AlignCenter)
        duty_editor.setValidator(duty_validator)
        duty_editor.textChanged.connect(self.check_inputs)
        self._duty_editor = duty_editor

        pressure_editor = QLineEdit(self)
        pressure_editor.setText("1.0")
        pressure_editor.setAlignment(Qt.AlignCenter)
        pressure_editor.setValidator(pressure_validator)
        pressure_editor.textChanged.connect(self.check_inputs)
        self._pressure_editor = pressure_editor

        factor_editor = QLineEdit(self)
        factor_editor.setText("0.8")
        factor_editor.setAlignment(Qt.AlignCenter)
        factor_editor.setValidator(factor_validator)
        factor_editor.textChanged.connect(self.check_inputs)
        self._factor_editor = factor_editor

        type_combo = QComboBox(self)
        arrang_combo = QComboBox(self)
        shell_combo = QComboBox(self)
        tube_combo = QComboBox(self)

        ex_list = ExchangerType.values_list()
        type_combo.addItems(ex_list)
        type_combo.currentTextChanged.connect(self._update_arrangment)
        type_combo.currentTextChanged.connect(self._update_shell_materials)

        shell_combo.currentTextChanged.connect(self._update_tube_materials)

        self._type_combo = type_combo
        self._arrang_combo = arrang_combo
        self._shell_combo = shell_combo
        self._tube_combo = tube_combo

        type_combo.setCurrentIndex(
            ex_list.index(ExchangerType.FLOATING_HEAD.value)
        )

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight)
        form_layout.setWidget(0, QFormLayout.LabelRole, label1)
        form_layout.setWidget(1, QFormLayout.LabelRole, label2)
        form_layout.setWidget(2, QFormLayout.LabelRole, label3)
        form_layout.setWidget(3, QFormLayout.LabelRole, label4)
        form_layout.setWidget(4, QFormLayout.LabelRole, label5)
        form_layout.setWidget(5, QFormLayout.LabelRole, label6)
        form_layout.setWidget(6, QFormLayout.LabelRole, label7)
        form_layout.setWidget(7, QFormLayout.LabelRole, label8)

        form_layout.setWidget(0, QFormLayout.FieldRole, id_edit)
        form_layout.setWidget(1, QFormLayout.FieldRole, duty_editor)
        form_layout.setWidget(2, QFormLayout.FieldRole, factor_editor)
        form_layout.setWidget(3, QFormLayout.FieldRole, type_combo)
        form_layout.setWidget(4, QFormLayout.FieldRole, arrang_combo)
        form_layout.setWidget(5, QFormLayout.FieldRole, shell_combo)
        form_layout.setWidget(6, QFormLayout.FieldRole, tube_combo)
        form_layout.setWidget(7, QFormLayout.FieldRole, pressure_editor)

        self.button_box = QDialogButtonBox(self)
        self.button_box.setOrientation(Qt.Horizontal)
        self.button_box.setStandardButtons(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )

        if self._ex_type == 'utility':
            # additional fields for utility exchanger input
            label9 = QLabel('Utility Inlet Temperature:', self)
            label10 = QLabel('Utility Outlet Temperature:', self)
            label11 = QLabel('Utility film coefficient:', self)

            ut_in_validator = QDoubleValidator(0.0, 1.0e9, _MAX_NUM_DIGITS)
            ut_out_validator = QDoubleValidator(0.0, 1.0e9, _MAX_NUM_DIGITS)
            ut_coef_validator = QDoubleValidator(0.0, 1.0e9, _MAX_NUM_DIGITS)

            ut_in_editor = QLineEdit(self)
            ut_in_editor.setAlignment(Qt.AlignCenter)
            ut_in_editor.setValidator(ut_in_validator)
            ut_in_editor.textChanged.connect(self.check_inputs)
            self._ut_in_editor = ut_in_editor

            ut_out_editor = QLineEdit(self)
            ut_out_editor.setAlignment(Qt.AlignCenter)
            ut_out_editor.setValidator(ut_out_validator)
            ut_out_editor.textChanged.connect(self.check_inputs)
            self._ut_out_editor = ut_out_editor

            ut_coef_editor = QLineEdit(self)
            ut_coef_editor.setAlignment(Qt.AlignCenter)
            ut_coef_editor.setValidator(ut_coef_validator)
            ut_coef_editor.textChanged.connect(self.check_inputs)
            self._ut_coef_editor = ut_coef_editor

            form_layout.setWidget(8, QFormLayout.LabelRole, label9)
            form_layout.setWidget(9, QFormLayout.LabelRole, label10)
            form_layout.setWidget(10, QFormLayout.LabelRole, label11)

            form_layout.setWidget(8, QFormLayout.FieldRole, ut_in_editor)
            form_layout.setWidget(9, QFormLayout.FieldRole, ut_out_editor)
            form_layout.setWidget(10, QFormLayout.FieldRole, ut_coef_editor)

        self.form_layout = form_layout

        # disable the ok button by default until the user inputs valid values
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)

        self.button_box.accepted.connect(self.accept)
        self.button_box.accepted.connect(self.on_ok_pressed)
        self.button_box.rejected.connect(self.reject)

        self.grid_layout = QGridLayout(self)
        self.grid_layout.addLayout(self.form_layout, 0, 0, 1, 1)
        self.grid_layout.addWidget(self.button_box, 1, 0, 1, 1)

    def _update_arrangment(self, ex: str) -> None:
        arrangements = COST_DATA.loc[(ex), :].index.get_level_values(
            'ARRANGEMENT').unique().tolist()

        self._arrang_combo.clear()
        self._arrang_combo.addItems(arrangements)

    def _update_shell_materials(self, ex: str) -> None:
        shells = MATERIAL_DATA.loc[(ex), :].index.get_level_values(
            'SHELL').unique()
        if shells.isna().any():
            nan_idx = shells.isna()
            shells = shells.values
            shells[nan_idx] = 'None'
        shells = shells.tolist()

        self._shell_combo.clear()
        self._shell_combo.addItems(shells)

    def _update_tube_materials(self, shell: str) -> None:
        if shell in ['', 'None']:
            return

        ex = self._type_combo.currentText()
        tube = MATERIAL_DATA.loc[(ex, shell), :].index.get_level_values(
            'TUBE').unique()
        if tube.isna().any():
            nan_idx = tube.isna()
            tube = tube.values
            tube[nan_idx] = 'None'
        tube = tube.tolist()

        self._tube_combo.clear()
        self._tube_combo.addItems(tube)

    def check_inputs(self):
        id_ex = self._id_edit.text()
        duty = self._duty_editor.text()
        pressure = self._pressure_editor.text()
        factor = self._factor_editor.text()

        state = self._duty_editor.validator().validate(id_ex, len(id_ex))[2]
        if state == QValidator.Acceptable or state == QValidator.Intermediate:
            is_id_valid = True
        else:
            is_id_valid = False

        is_duty_valid = _is_value_valid(duty)

        is_pressure_valid = _is_value_valid(
            pressure, self._pressure_editor.validator()
        )

        is_factor_valid = _is_value_valid(
            factor, self._ut_in_editor.validator()
        )

        all_checks = [
            is_id_valid,
            is_duty_valid,
            is_pressure_valid,
            is_factor_valid
        ]

        if self._ex_type == 'utility':
            ut_in = self._ut_in_editor.text()
            ut_out = self._ut_out_editor.text()
            ut_coef = self._ut_coef_editor.text()

            is_ut_in_valid = _is_value_valid(
                ut_in, self._ut_in_editor.validator()
            )

            is_ut_out_valid = _is_value_valid(
                ut_out, self._ut_out_editor.validator()
            )

            is_ut_coef_valid = _is_value_valid(
                ut_coef, self._ut_coef_editor.validator()
            )

            all_checks.extend([
                is_ut_in_valid,
                is_ut_out_valid,
                is_ut_coef_valid
            ])

        if all(all_checks):
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)
        else:
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)

    def on_ok_pressed(self):
        ex_id = self._id_edit.text()
        ex_duty = float(self._duty_editor.text())
        ex_type = ExchangerType(self._type_combo.currentText())
        ex_arr = ArrangementType(self._arrang_combo.currentText())
        ex_shell = MaterialType(self._shell_combo.currentText())
        ex_tube = MaterialType(self._tube_combo.currentText())
        ex_pres = float(self._pressure_editor.text())
        ex_factor = float(self._factor_editor.text())

        if self._ex_type == 'process':
            self._setup.add_exchanger(self._des_type, ex_id, ex_duty,
                                      self._interval, self._source, self._dest,
                                      ex_type, ex_arr, ex_shell, ex_tube,
                                      ex_pres, ex_factor)
        else:
            if self._dest == 'Cold utility':
                util_type = 'cold'
                stream_id = self._source
            elif self._source == 'Hot utility':
                util_type = 'hot'
                stream_id = self._dest

            ut_in = float(self._ut_in_editor.text())
            ut_out = float(self._ut_out_editor.text())
            ut_coef = float(self._ut_coef_editor.text())

            try:
                self._setup.add_utility_exchanger(
                    self._des_type, ex_id, ex_duty,
                    self._interval, util_type, stream_id,
                    ut_in, ut_out, ut_coef,
                    ex_type, ex_arr, ex_shell, ex_tube, ex_pres, ex_factor
                )
            except ValueError as err:
                err_msg = str(err)

                if 'outside allowed' in err_msg:
                    # just warn the user, do not raise exception
                    msg_box = QMessageBox(
                        QMessageBox.Warning,
                        'Invalid input value.',
                        err_msg,
                        buttons=QMessageBox.Ok,
                        parent=None
                    )
                    msg_box.exec_()

                else:
                    # do not treat exception, just re-raise it
                    raise err


class SplitStreamDialog(QDialog):
    _flowrates_changed = pyqtSignal()

    def __init__(self, stream_id: str, stream_type: str,
                 scene: PinchDesignScene, parent=None):
        super().__init__(parent=parent)

        self._scene = scene

        self._stream_id = stream_id
        self._stream_type = stream_type
        self._des_type = scene._des_type
        self._setup = scene._setup
        init_rows = 2
        base_flow = self._get_base_flow_split() / init_rows
        self._flowrates = [base_flow] * init_rows

        self.createUi()

    def createUi(self):
        self.setWindowModality(Qt.WindowModal)
        self.setModal(True)
        self.setWindowTitle("Split stream '{0}'".format(self._stream_id))
        self.resize(250, 250)

        label1 = QLabel(
            "# of streams to split '{0}' into:".format(self._stream_id),
            self
        )

        flow_validator = QIntValidator(2, 5)

        flow_edit = QLineEdit(str(len(self._flowrates)), self)
        flow_edit.setAlignment(Qt.AlignCenter)
        flow_edit.setValidator(flow_validator)
        flow_edit.textChanged.connect(self._update_flow_rates)
        self._flow_edit = flow_edit

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight)
        form_layout.setWidget(0, QFormLayout.LabelRole, label1)
        form_layout.setWidget(0, QFormLayout.FieldRole, flow_edit)

        table_view = QTableView(self)
        table_model = StreamSplitTableModel(self, table_view)
        table_view.setModel(table_model)
        table_view.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        button_box = QDialogButtonBox(self)
        button_box.setOrientation(Qt.Horizontal)
        button_box.setStandardButtons(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.accepted.connect(self._split_streams)
        button_box.rejected.connect(self.reject)

        grid_layout = QGridLayout(self)
        grid_layout.addLayout(form_layout, 0, 0, 1, 1)
        grid_layout.addWidget(table_view, 1, 0, 1, 1)
        grid_layout.addWidget(button_box, 2, 0, 1, 1)

    def _get_base_flow_split(self) -> float:
        if self._des_type == 'abv':
            if self._stream_type == 'hot':
                streams = self._setup.hot_above
            else:
                streams = self._setup.cold_above

        else:
            if self._stream_type == 'hot':
                streams = self._setup.hot_below
            else:
                streams = self._setup.cold_below

        stream = streams.set_index(STFCFM.ID.name).loc[self._stream_id, :]

        return stream.at[STFCFM.FLOW.name]

    def _update_flow_rates(self) -> int:
        try:
            n_rows = int(self._flow_edit.text())
        except:
            pass
        else:
            validator = self._flow_edit.validator()
            if validator.bottom() <= n_rows <= validator.top():
                base_flow = self._get_base_flow_split() / n_rows
                self._flowrates = [base_flow] * n_rows
                self._flowrates_changed.emit()

    def _split_streams(self):
        self._setup.split_stream(self._des_type, self._stream_type,
                                 self._stream_id, self._flowrates)
        self._scene.paint_interval_diagram()
        self._scene.paint_exchangers()


class StreamSplitTableModel(QAbstractTableModel):
    def __init__(self, dialog: SplitStreamDialog, parent: QTableView):
        super().__init__(parent=parent)
        self._dialog = dialog
        self._load_flowrates()
        dialog._flowrates_changed.connect(self._load_flowrates)

    def _load_flowrates(self):
        self.layoutAboutToBeChanged.emit()
        self._flowrates = self._dialog._flowrates
        self.layoutChanged.emit()

    def rowCount(self, parent: QModelIndex = None) -> int:
        return len(self._flowrates)

    def columnCount(self, parent: QModelIndex = None) -> int:
        return 1

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()

        if role == Qt.DisplayRole:
            return str(self._flowrates[row])

        else:
            return None


def _is_value_valid(value: float, validator: QValidator = None) -> bool:
    try:
        value = float(value)
    except ValueError as ex:
        return False
    else:
        if validator is None:
            return True
        else:
            bottom = validator.bottom()
            top = validator.top()

            if bottom <= value <= top:
                return True
            else:
                return False


if __name__ == "__main__":
    import sys
    import pathlib

    hsd_filepath = pathlib.Path().resolve() / "tests" / "hsdtest.hsd"

    setup = Setup()
    setup.load(str(hsd_filepath))

    app = QApplication(sys.argv)

    w = PinchDesignDialog(setup, str(hsd_filepath))
    w.show()

    sys.exit(app.exec_())
