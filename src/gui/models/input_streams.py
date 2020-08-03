import numpy as np
from pandas import Series
from PyQt5.QtCore import (
    QAbstractItemModel, QAbstractTableModel, QModelIndex, QRegExp, Qt)
from PyQt5.QtGui import (QBrush, QDoubleValidator, QFont, QPalette,
                         QRegExpValidator)
from PyQt5.QtWidgets import (QItemDelegate, QLineEdit, QStyleOptionViewItem,
                             QTableView, QWidget)

from .core import Setup, STFM, FCFM

_BOLD_HEADER_FONT = QFont()
_BOLD_HEADER_FONT.setBold(True)

_MAX_NUM_DIGITS = 10


class StreamIdDelegate(QItemDelegate):
    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem,
                     index: QModelIndex):
        line_editor = QLineEdit(parent)
        reg_ex = QRegExp("^[A-Z$a-z$0-9][a-z_$0-9]{,9}$")
        input_validator = QRegExpValidator(reg_ex, line_editor)
        line_editor.setValidator(input_validator)

        return line_editor


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
        double_validator = QDoubleValidator(
            0.0, 100, _MAX_NUM_DIGITS,
            parent=line_editor)
        line_editor.setValidator(double_validator)

        return line_editor


class StreamEditorDelegate(DoubleEditorDelegate):
    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem,
                     index: QModelIndex):
        line_editor = QLineEdit(parent)
        line_editor.setAlignment(Qt.AlignCenter)
        double_validator = QDoubleValidator(
            0.0, 1.0e9, _MAX_NUM_DIGITS, parent=line_editor
        )
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
            min_temp, max_temp, _MAX_NUM_DIGITS, parent=line_editor
        )
        line_editor.setValidator(double_validator)

        return line_editor


class FilmCoefficientEditorDelegate(DoubleEditorDelegate):
    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem,
                     index: QModelIndex):
        line_editor = QLineEdit(parent)
        line_editor.setAlignment(Qt.AlignCenter)
        min_coeff = 0.0  # 0
        max_coeff = 1e4  # 10000
        double_validator = QDoubleValidator(
            min_coeff, max_coeff, _MAX_NUM_DIGITS, parent=line_editor
        )
        line_editor.setValidator(double_validator)

        return line_editor


class StreamInputTableModel(QAbstractTableModel):

    def __init__(self, setup: Setup, stream_type: str, parent: QTableView):
        super().__init__(parent=parent)
        self._setup = setup
        self._unit_set = setup.units
        self._stream_type = stream_type
        self.update_stream_table()

        self._setup.hot_changed.connect(self.update_stream_table)
        self._setup.cold_changed.connect(self.update_stream_table)
        self._setup.dt_changed.connect(self.update_stream_table)

        self._setup.units_changed.connect(self.update_header_data)

    def update_stream_table(self):
        self.layoutAboutToBeChanged.emit()

        if self._stream_type == 'hot':
            self._input_table = self._setup.hot
        elif self._stream_type == 'cold':
            self._input_table = self._setup.cold

        self.layoutChanged.emit()

    def update_header_data(self):
        self._unit_set = self._setup.units
        self.headerDataChanged.emit(Qt.Horizontal, 0, self.columnCount())

    def rowCount(self, parent: QModelIndex = None):
        return len(self._input_table)

    def columnCount(self, parent: QModelIndex = None):
        return len(self._input_table.columns)

    def headerData(self, section: int, orientation=Qt.Orientation,
                   role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                hval = STFM.headers()[section]
                header = self._unit_set.enum_with_unit(STFM(hval))
                return header
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
        colname = self._input_table.columns[col]

        value = self._input_table.at[
            row,
            colname
        ]

        if role == Qt.DisplayRole:
            if colname == STFM.ID.name:
                return str(value)
            else:
                return "{0:.6g}".format(value)
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        elif role == Qt.BackgroundRole:
            if colname == STFM.ID.name:
                counts = self._input_table.loc[:, colname].value_counts()
                if counts[value] > 1:
                    return QBrush(Qt.red)
                else:
                    QBrush(self.parent().palette().brush(QPalette.Base))
        else:
            return None

    def setData(self, index: QModelIndex, value, role: int = Qt.EditRole):
        if role != Qt.EditRole or not index.isValid():
            return False

        row = index.row()
        col = index.column()
        colname = self._input_table.columns[col]

        if colname == STFM.ID.name:
            value = str(value)
        else:
            value = float(value)

        self._input_table.at[row, colname] = value
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


class StreamFilmCoeffTableModel(QAbstractTableModel):
    def __init__(self, setup: Setup, stream_type: str, parent: QTableView):
        super().__init__(parent=parent)
        self._setup = setup
        self._unit_set = setup.units
        self._stream_type = stream_type
        self.update_stream_table()

        self._setup.hot_coeffs_changed.connect(self.update_stream_table)
        self._setup.cold_coeffs_changed.connect(self.update_stream_table)

        self._setup.units_changed.connect(self.update_header_data)

    def update_stream_table(self):
        self.layoutAboutToBeChanged.emit()

        if self._stream_type == 'hot':
            self._input_table = self._setup.hot_film_coef
        elif self._stream_type == 'cold':
            self._input_table = self._setup.cold_film_coef

        self.layoutChanged.emit()

    def update_header_data(self):
        self._unit_set = self._setup.units
        self.headerDataChanged.emit(Qt.Horizontal, 0, self.columnCount())

    def rowCount(self, parent: QModelIndex = None):
        return len(self._input_table)

    def columnCount(self, parent: QModelIndex = None):
        return 1

    def headerData(self, section: int, orientation=Qt.Orientation,
                   role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                header = self._unit_set.enum_with_unit(FCFM.COEF)
                return header
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

        value = self._input_table.at[row, FCFM.COEF.name]

        if role == Qt.DisplayRole:
            if np.isnan(value):
                return None
            else:
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

        self._input_table.at[row, FCFM.COEF.name] = float(value)
        if self._stream_type == 'hot':
            self._setup.hot_coeffs_changed.emit()
        else:
            self._setup.cold_coeffs_changed.emit()

        self.dataChanged.emit(
            index.sibling(0, 0),
            index.sibling(self.rowCount() - 1, self.columnCount() - 1)
        )

        return True

    def flags(self, index: QModelIndex):
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
