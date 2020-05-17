import numpy as np
from pandas import Series
from PyQt5.QtCore import (
    QAbstractItemModel, QAbstractTableModel, QModelIndex, Qt)
from PyQt5.QtGui import QDoubleValidator, QFont
from PyQt5.QtWidgets import (QItemDelegate, QLineEdit, QStyleOptionViewItem,
                             QTableView, QWidget)

from .core import Setup, StreamFrameMapper

_BOLD_HEADER_FONT = QFont()
_BOLD_HEADER_FONT.setBold(True)


class DoubleEditorDelegate(QItemDelegate):
    def setEditorData(self, editor: QWidget, index=QModelIndex):
        current_text = index.data(role=Qt.DisplayRole)

        if isinstance(editor, QLineEdit):
            editor.setText(current_text)

    def setModelData(self, editor: QWidget, model: QAbstractItemModel,
                     index: QModelIndex):
        text = editor.text()

        model.setData(index, text, Qt.EditRole)

    def updateEditorGeometry(self, editor: QWidget,
                             option: QStyleOptionViewItem, index: QModelIndex):
        editor.setGeometry(option.rect)


class PositiveDoubleEditorDelegate(DoubleEditorDelegate):
    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem,
                     index: QModelIndex):
        line_editor = QLineEdit(parent)
        line_editor.setAlignment(Qt.AlignCenter)
        double_validator = QDoubleValidator(0.0, 100, 6, parent=line_editor)
        line_editor.setValidator(double_validator)

        return line_editor


class StreamEditorDelegate(DoubleEditorDelegate):
    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem,
                     index: QModelIndex):
        line_editor = QLineEdit(parent)
        line_editor.setAlignment(Qt.AlignCenter)
        double_validator = QDoubleValidator(0.0, 1.0e9, 6, parent=line_editor)
        line_editor.setValidator(double_validator)

        return line_editor


class TemperatureEditorDelegate(DoubleEditorDelegate):
    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem,
                     index: QModelIndex):
        line_editor = QLineEdit(parent)
        line_editor.setAlignment(Qt.AlignCenter)
        min_temp = -459.67  # 0K in Fahrenheit
        max_temp = 18032.0  # 10000 C in Fahrenheit
        double_validator = QDoubleValidator(
            min_temp, max_temp, 3, parent=line_editor
        )
        line_editor.setValidator(double_validator)

        return line_editor


class StreamInputTableModel(QAbstractTableModel):

    def __init__(self, setup: Setup, stream_type: str, parent: QTableView):
        super().__init__(parent=parent)
        self._setup = setup
        self._stream_type = stream_type
        self.update_stream_table()

        self._setup.hot_changed.connect(self.update_stream_table)
        self._setup.cold_changed.connect(self.update_stream_table)
        self._setup.dt_changed.connect(self.update_stream_table)

    def update_stream_table(self):
        self.layoutAboutToBeChanged.emit()

        if self._stream_type == 'hot':
            self._input_table = self._setup.hot
        elif self._stream_type == 'cold':
            self._input_table = self._setup.cold

        self.layoutChanged.emit()

    def rowCount(self, parent: QModelIndex = None):
        return len(self._input_table)

    def columnCount(self, parent: QModelIndex = None):
        return len(self._input_table.columns)

    def headerData(self, section: int, orientation=Qt.Orientation,
                   role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return StreamFrameMapper.headers()[section]
            else:
                return self._input_table.index[section] + 1

        elif role == Qt.FontRole:
            return _BOLD_HEADER_FONT

        else:
            return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        value = self._input_table.at[
            row,
            self._input_table.columns[col]
        ]

        if role == Qt.DisplayRole:
            return "{0:.6g}".format(value)
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        else:
            return None

    def setData(self, index: QModelIndex, value, role: int = Qt.EditRole):
        if role != Qt.EditRole or not index.isValid():
            return False

        row = index.row()
        col = index.column()

        self._input_table.at[row,
                             self._input_table.columns[col]] = float(value)
        if self._stream_type == 'hot':
            self._setup.hot_changed.emit()
        else:
            self._setup.cold_changed.emit()

        self.dataChanged.emit(
            index.sibling(0, 0),
            index.sibling(self.rowCount() - 1, self.columnCount() - 1)
        )

        return True

    def flags(self, index: QModelIndex):
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
