import pandas as pd
from PyQt5.QtCore import (
    QAbstractItemModel, QAbstractTableModel, QModelIndex, Qt, pyqtSignal)
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QTableView

from .core import Setup, SummaryFrameMapper

_HEADER_FONT = QFont()
_HEADER_FONT.setBold(True)

SFM = SummaryFrameMapper


class SummaryModel(QAbstractTableModel):

    def __init__(self, setup: Setup, parent: QTableView):
        super().__init__(parent=parent)
        self._setup = setup
        self._unit_set = setup.units
        setup.hot_changed.connect(self.update_summary)
        setup.cold_changed.connect(self.update_summary)
        setup.dt_changed.connect(self.update_summary)

        self._setup.units_changed.connect(self.update_header_data)

        self.update_summary()

    def update_summary(self):
        self.layoutAboutToBeChanged.emit()

        self._summary = self._setup.summary

        self.layoutChanged.emit()

    def update_header_data(self):
        self._unit_set = self._setup.units
        self.headerDataChanged.emit(Qt.Horizontal, 0, self.columnCount())

    def rowCount(self, parent: QModelIndex = QModelIndex()):
        return len(self._summary)

    def columnCount(self, parent: QModelIndex = QModelIndex()):
        return len(self._summary.columns) - 2

    def headerData(self, section: int, orientation=Qt.Orientation,
                   role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                sec = SFM.headers()[section]
                if sec not in [SFM.HOTSTRIDX.value, SFM.COLDSTRIDX.value]:
                    return self._unit_set.enum_with_unit(SFM(sec))
            else:
                return None

        elif role == Qt.FontRole:
            return _HEADER_FONT

        else:
            return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        value = self._summary.at[row, self._summary.columns[col]]

        if role == Qt.DisplayRole:
            if isinstance(value, float):
                return "{0:.6g}".format(value)
            else:
                return str(value)
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        else:
            return None
