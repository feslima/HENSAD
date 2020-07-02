import numpy as np
import pandas as pd
from matplotlib.backends.backend_qt5agg import (FigureCanvasQTAgg,
                                                NavigationToolbar2QT)
from matplotlib.figure import Figure
from PyQt5.QtCore import QAbstractTableModel, QModelIndex, QSize, Qt
from PyQt5.QtGui import QFont, QResizeEvent
from PyQt5.QtWidgets import (QApplication, QComboBox, QDialog, QFormLayout,
                             QFrame, QGridLayout, QGroupBox, QHeaderView,
                             QLabel, QLineEdit, QPushButton, QSizePolicy,
                             QSlider, QSpacerItem, QSpinBox, QTableView)

from gui.models.core import Setup
from hensad import ArrangementType, ExchangerType, MaterialType, calculate_eaoc
from hensad.cost import COST_DATA, MATERIAL_DATA

_BOLD_HEADER_FONT = QFont()
_BOLD_HEADER_FONT.setBold(True)

_HEADER_MAP = {
    'dt': 'DT',
    'eaoc': 'EAOC',
    'huq': 'Hot utility',
    'cuq': 'Cold utility',
    'netarea': 'Area',
    'n_ex': 'Number of exchangers'
}


class EAOCTableModel(QAbstractTableModel):
    def __init__(self, frame: pd.DataFrame, parent: QTableView):
        super().__init__(parent=parent)

        self._frame = frame
        self._update_frame(frame)

    def _update_frame(self, frame: pd.DataFrame) -> None:
        self.layoutAboutToBeChanged.emit()

        self._frame = frame

        self.layoutChanged.emit()

    def rowCount(self, parent: QModelIndex = None):
        return len(self._frame)

    def columnCount(self, parent: QModelIndex = None):
        return len(self._frame.columns)

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return _HEADER_MAP[self._frame.columns[section]]
            else:
                return None

        elif role == Qt.FontRole:
            return _BOLD_HEADER_FONT

        else:
            return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        colname = self._frame.columns[col]

        value = self._frame.at[row, colname]

        if role == Qt.DisplayRole:
            return "{0:.6g}".format(value)

        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

        else:
            return None


class EAOCDialog(QDialog):
    def __init__(self, setup: Setup):
        super().__init__()
        self.setWindowFlags(Qt.Window)
        self.setWindowTitle("EAOC - DT plot")
        self.setMinimumSize(800, 600)

        self._setup = setup

        self._createUi()

        # self._plot_graph()

    def _createUi(self) -> None:
        input_box = self._createUi_input_box()

        table_view = QTableView(self)
        self._table_model = EAOCTableModel(
            pd.DataFrame(columns=list(_HEADER_MAP.keys())),
            table_view
        )
        table_view.setModel(self._table_model)
        table_view.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        table_view.setMaximumHeight(300)

        self._eaoc_figure = Figure()
        self._eaoc_canvas = FigureCanvasQTAgg(self._eaoc_figure)
        self._eaoc_plt_tbar = NavigationToolbar2QT(self._eaoc_canvas, self)

        self._util_figure = Figure()
        self._util_canvas = FigureCanvasQTAgg(self._util_figure)
        self._util_plt_tbar = NavigationToolbar2QT(self._util_canvas, self)

        layout = QGridLayout()
        layout.addWidget(input_box, 0, 0, 1, 1)
        layout.addWidget(table_view, 0, 1, 1, 3)
        layout.addWidget(self._eaoc_canvas, 1, 0, 1, 2)
        layout.addWidget(self._eaoc_plt_tbar, 2, 0, 1, 2, Qt.AlignCenter)
        layout.addWidget(self._util_canvas, 1, 2, 1, 2)
        layout.addWidget(self._util_plt_tbar, 2, 2, 1, 2, Qt.AlignCenter)
        self.setLayout(layout)

    def _createUi_input_box(self) -> QGroupBox:
        input_box = QGroupBox(self)
        box_size_policy = QSizePolicy(QSizePolicy.Preferred,
                                      QSizePolicy.Preferred)
        box_size_policy.setHorizontalStretch(0)
        box_size_policy.setVerticalStretch(0)
        box_size_policy.setHeightForWidth(
            input_box.sizePolicy().hasHeightForWidth()
        )
        input_box.setSizePolicy(box_size_policy)
        input_box.setTitle("")
        input_box.setMinimumSize(QSize(250, 300))
        input_box.setMaximumSize(QSize(250, 300))

        font = QFont()
        font.setBold(True)

        label1 = QLabel("Plot definition", self)
        label1.setFont(font)

        line1 = QFrame(input_box)
        line1.setFrameShape(QFrame.HLine)
        line1.setFrameShadow(QFrame.Sunken)

        label2 = QLabel("Min ΔT:", self)
        label3 = QLabel("Max ΔT:", self)
        label4 = QLabel("# of points:", self)
        label5 = QLabel("Exchanger type:", self)
        label6 = QLabel("Tube Arrangement:", self)
        label7 = QLabel("Shell side material:", self)
        label8 = QLabel("Tube side material:", self)
        label9 = QLabel("Operating pressure:", self)

        min_dt_edit = QLineEdit(self)
        max_dt_edit = QLineEdit(self)
        num_pt_edit = QLineEdit(self)
        ex_typ_cbb = QComboBox(self)
        arrang_cbb = QComboBox(self)
        shell_cbb = QComboBox(self)
        tube_cbb = QComboBox(self)
        press_edit = QLineEdit(self)

        min_dt_edit.setText('5')
        max_dt_edit.setText('30')
        num_pt_edit.setText('10')
        press_edit.setText('1')

        min_dt_edit.setAlignment(Qt.AlignCenter)
        max_dt_edit.setAlignment(Qt.AlignCenter)
        num_pt_edit.setAlignment(Qt.AlignCenter)
        press_edit.setAlignment(Qt.AlignCenter)

        ex_list = ExchangerType.values_list()
        ex_typ_cbb.addItems(ex_list)
        ex_typ_cbb.currentTextChanged.connect(self._update_arrangment)
        ex_typ_cbb.currentTextChanged.connect(self._update_shell_materials)
        
        shell_cbb.currentTextChanged.connect(self._update_tube_materials)

        self._ex_typ_cbb = ex_typ_cbb
        self._arrang_cbb = arrang_cbb
        self._shell_cbb = shell_cbb
        self._tube_cbb = tube_cbb

        ex_typ_cbb.setCurrentIndex(
            ex_list.index(ExchangerType.FLOATING_HEAD.value)
        )

        self._min_dt_edit = min_dt_edit
        self._max_dt_edit = max_dt_edit
        self._num_pt_edit = num_pt_edit
        self._press_edit = press_edit

        spacer = QSpacerItem(20, 40,
                             QSizePolicy.Minimum, QSizePolicy.Expanding)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight)
        form_layout.setWidget(0, QFormLayout.LabelRole, label2)
        form_layout.setWidget(1, QFormLayout.LabelRole, label3)
        form_layout.setWidget(2, QFormLayout.LabelRole, label4)
        form_layout.setWidget(3, QFormLayout.LabelRole, label5)
        form_layout.setWidget(4, QFormLayout.LabelRole, label6)
        form_layout.setWidget(5, QFormLayout.LabelRole, label7)
        form_layout.setWidget(6, QFormLayout.LabelRole, label8)
        form_layout.setWidget(7, QFormLayout.LabelRole, label9)

        form_layout.setWidget(0, QFormLayout.FieldRole, min_dt_edit)
        form_layout.setWidget(1, QFormLayout.FieldRole, max_dt_edit)
        form_layout.setWidget(2, QFormLayout.FieldRole, num_pt_edit)
        form_layout.setWidget(3, QFormLayout.FieldRole, ex_typ_cbb)
        form_layout.setWidget(4, QFormLayout.FieldRole, arrang_cbb)
        form_layout.setWidget(5, QFormLayout.FieldRole, shell_cbb)
        form_layout.setWidget(6, QFormLayout.FieldRole, tube_cbb)
        form_layout.setWidget(7, QFormLayout.FieldRole, press_edit)

        pushbutton = QPushButton('Plot data', self)
        pushbutton.clicked.connect(self._plot_graph)

        layout = QGridLayout(input_box)
        layout.addWidget(label1, 0, 0, 1, 1)
        layout.addWidget(line1, 1, 0, 1, 1)
        layout.addLayout(form_layout, 2, 0, 1, 1)
        layout.addWidget(pushbutton, 3, 0, 1, 1)
        layout.addItem(spacer, 4, 0, 1, 1)

        return input_box

    def _plot_graph(self) -> None:
        try:
            DTMIN = float(self._min_dt_edit.text())
            DTMAX = float(self._max_dt_edit.text())
            NPTS = int(self._num_pt_edit.text())
            PRESS = float(self._press_edit.text())
        except ValueError as e:
            # invalid values for inputs
            return
        else:
            PTS = np.linspace(DTMIN, DTMAX, NPTS, dtype=float)
            ex = ExchangerType(self._ex_typ_cbb.currentText())
            arrangement = ArrangementType(self._arrang_cbb.currentText())
            shell = MaterialType(self._shell_cbb.currentText())
            tube = MaterialType(self._tube_cbb.currentText())
        
        hot = self._setup.hot
        cold = self._setup.cold
        hot_coef = self._setup.hot_film_coef
        cold_coef = self._setup.cold_film_coef

        new_rows = []
        for dt in PTS:
            eaoc, netarea, huq, cuq, n_ex = calculate_eaoc(
                hot, cold, dt, hot_coef, cold_coef,
                ex, arrangement, shell, tube,
                PRESS
            )
            new_rows.append([
                {
                    'dt': dt,
                    'eaoc': eaoc,
                    'netarea': netarea,
                    'huq': huq,
                    'cuq': cuq,
                    'n_ex': n_ex
                }
            ]
            )

        df = pd.concat([pd.DataFrame(row) for row in new_rows],
                       ignore_index=True)

        self._table_model._update_frame(df)

        self._eaoc_figure.clear()
        ax1 = self._eaoc_figure.add_subplot(111)
        ax1.plot(df['dt'], df['eaoc'], color='b')
        ax1.set_xlabel('$\Delta T$')
        ax1.set_ylabel('EAOC ($/y)')
        ax1.set_title('EAOC sensitivity')
        ax1.grid(which='both')
        self._eaoc_figure.canvas.draw()
        self._eaoc_figure.tight_layout()

        self._util_figure.clear()
        ax2 = self._util_figure.add_subplot(111)
        ax2.plot(df['dt'], df['netarea'], color='k', label='Area')
        ax2.set_xlabel('$\Delta T$')
        ax2.set_ylabel('Network area')
        ax2.set_title('Heat Exchanger Network area')
        ax2.legend()
        ax2.grid(which='both')

        ax2_1 = ax2.twinx()
        ax2_1.plot(df['dt'], df['huq'], color='r', label='Hot')
        ax2_1.plot(df['dt'], df['cuq'], color='b', label='Cold')
        ax2_1.set_ylabel('Utility load')
        ax2_1.legend()
        self._util_figure.canvas.draw()
        self._util_figure.tight_layout()

    def _update_arrangment(self, ex: str) -> None:
        arrangements = COST_DATA.loc[(ex), :].index.get_level_values(
            'ARRANGEMENT').unique().tolist()

        self._arrang_cbb.clear()
        self._arrang_cbb.addItems(arrangements)

    def _update_shell_materials(self, ex: str) -> None:
        shells = MATERIAL_DATA.loc[(ex), :].index.get_level_values(
            'SHELL').unique()
        if shells.isna().any():
            nan_idx = shells.isna()
            shells = shells.values
            shells[nan_idx] = 'None'
        shells = shells.tolist()

        self._shell_cbb.clear()
        self._shell_cbb.addItems(shells)
    
    def _update_tube_materials(self, shell: str) -> None:
        if shell in ['', 'None']:
            return

        ex = self._ex_typ_cbb.currentText()
        tube = MATERIAL_DATA.loc[(ex, shell), :].index.get_level_values(
            'TUBE').unique()
        if tube.isna().any():
            nan_idx = tube.isna()
            tube = tube.values
            tube[nan_idx] = 'None'
        tube = tube.tolist()

        self._tube_cbb.clear()
        self._tube_cbb.addItems(tube)

    def resizeEvent(self, event: QResizeEvent):
        self._eaoc_figure.tight_layout()
        self._util_figure.tight_layout()
        return super().resizeEvent(event)


if __name__ == "__main__":
    import sys
    import pathlib

    hsd_filepath = pathlib.Path().resolve() / "tests" / "hsdtest.hsd"

    setup = Setup()
    setup.load(str(hsd_filepath))

    app = QApplication(sys.argv)

    w = EAOCDialog(setup)
    w.show()

    sys.exit(app.exec_())
