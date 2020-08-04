import numpy as np
import pandas as pd
from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QTableView

from gui.models.core import HEDFM, HEDFM_STR_COLS, Setup

_BOLD_HEADER_FONT = QFont()
_BOLD_HEADER_FONT.setBold(True)


class ExchangerDesignTableModel(QAbstractTableModel):
    def __init__(self, setup: Setup, design_type: str, parent: QTableView):
        super().__init__(parent=parent)

        self._design_type = design_type
        self._setup = setup
        self._unit_set = setup.units

        self._load_design()

        if design_type == 'abv':
            self._setup.design_above_changed.connect(self._load_design)
        else:
            self._setup.design_below_changed.connect(self._load_design)

        self._setup.units_changed.connect(self.update_header_data)

    def _load_design(self):
        self.layoutAboutToBeChanged.emit()

        if self._design_type == 'abv':
            self._design = self._setup.design_above
        else:
            self._design = self._setup.design_below

        self.layoutChanged.emit()

    def update_header_data(self):
        self._unit_set = self._setup.units
        self.headerDataChanged.emit(Qt.Horizontal, 0, self.columnCount())

    def rowCount(self, parent: QModelIndex = None):
        return len(self._design)

    def columnCount(self, parent: QModelIndex = None):
        return len(self._design.columns)

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                hval = HEDFM.headers()[section]
                header = self._unit_set.enum_with_unit(HEDFM(hval))
                return header
            else:
                return self._design.index[section] + 1

        elif role == Qt.FontRole:
            return _BOLD_HEADER_FONT

        else:
            return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        colname = self._design.columns[col]

        value = self._design.at[row, colname]

        if role == Qt.DisplayRole:
            if colname in HEDFM_STR_COLS:
                return str(value)
            else:
                return "{0:.6g}".format(value)

        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

        else:
            return None
