import json
import pathlib
import sys

if getattr(sys, 'frozen', False):
    pkg_dir = sys._MEIPASS
else:
    pkg_dir = str(pathlib.Path(__file__).resolve().parent.parent)

sys.path.append(pkg_dir)

import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import (QApplication, QFileDialog, QHeaderView,
                             QMainWindow, QTableView)

from gui.base import my_exception_hook
from gui.models.core import (FilmCoefficientsFrameMapper, Setup, SIUnits,
                             StreamFrameMapper, USUnits)
from gui.models.input_streams import (FilmCoefficientEditorDelegate,
                                      StreamEditorDelegate,
                                      StreamFilmCoeffTableModel,
                                      StreamIdDelegate, StreamInputTableModel,
                                      TemperatureEditorDelegate)
from gui.models.summary_table import SummaryModel
from gui.views.designs.pinchdesign import PinchDesignDialog
from gui.views.diagrams.cascade import CascadeDiagramDialog
from gui.views.diagrams.eaoc import EAOCDialog
from gui.views.diagrams.enthalpy import CompositeEnthalpyDialog
from gui.views.diagrams.temperatureinterval import \
    TemperatureIntervalDiagramDialog
from gui.views.py.mainwindow import Ui_MainWindow

DEFAULT_DT = 10


class MinTempApproachValidator(QIntValidator):
    def fixup(self, inp: str):
        if inp == '':
            inp = str(DEFAULT_DT)
        return inp


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowState(Qt.WindowMaximized)
        self.setWindowTitle('HENSAD - untitled.hsd')

        # --------------------- Widget Initialization -------------------------
        self._setup = Setup()

        hot_table = self.ui.hotStreamTableView
        hot_model = StreamInputTableModel(self._setup, 'hot', hot_table)
        hot_table.setModel(hot_model)
        self._hot_delegates = []

        hot_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.set_input_table_delegates('hot')

        hot_coef_table = self.ui.hotFilmCoefTableView
        hot_coef_model = StreamFilmCoeffTableModel(
            self._setup, 'hot', hot_coef_table
        )
        hot_coef_table.setModel(hot_coef_model)

        hot_coef_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.set_film_coef_delegates('hot')

        cold_table = self.ui.coldStreamTableView
        cold_model = StreamInputTableModel(self._setup, 'cold', cold_table)
        cold_table.setModel(cold_model)
        self._cold_delegates = []

        cold_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.set_input_table_delegates('cold')

        cold_coef_table = self.ui.coldFilmCoefTableView
        cold_coef_model = StreamFilmCoeffTableModel(
            self._setup, 'cold', cold_coef_table
        )
        cold_coef_table.setModel(cold_coef_model)

        cold_coef_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.set_film_coef_delegates('cold')

        summary_table = self.ui.summaryTableView
        summary_model = SummaryModel(self._setup, summary_table)
        summary_table.setModel(summary_model)

        summary_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        # DT approach editor
        dt_validator = MinTempApproachValidator(
            1, 300, parent=self.ui.dtApproachLineEdit
        )
        self.ui.dtApproachLineEdit.setValidator(dt_validator)

        # ----------------------------- Actions -------------------------------
        self.ui.actionSave.triggered.connect(self.save_file)
        self.ui.actionOpen.triggered.connect(self.open_file)
        self.ui.actionSave_as.triggered.connect(self.save_file_as)

        # ----------------------------- Signals -------------------------------
        self.ui.addHotStreamPushButton.clicked.connect(
            self.on_add_hot_stream_clicked
        )
        self.ui.deleteHotStreamPushButton.clicked.connect(
            self.on_del_hot_stream_clicked
        )

        self.ui.addColdStreamPushButton.clicked.connect(
            self.on_add_cold_stream_clicked
        )
        self.ui.deleteColdStreamPushButton.clicked.connect(
            self.on_del_cold_stream_clicked
        )

        self.ui.dtApproachLineEdit.editingFinished.connect(
            self.on_approach_temp_changed
        )

        self.ui.tiDiagramPushButton.clicked.connect(
            self.open_interval_diagram
        )

        self.ui.cascadeDiagramPushButton.clicked.connect(
            self.open_cascade_diagram
        )

        self.ui.tqDiagramPushButton.clicked.connect(
            self.open_enthalpy_diagram
        )

        self.ui.designToolPushButton.clicked.connect(
            self.open_network_design
        )

        self.ui.eaocPlotPushButton.clicked.connect(
            self.open_eaoc_plot
        )
        self.ui.unitsComboBox.currentTextChanged.connect(
            self.update_setup_units
        )

        self._setup.hot_changed.connect(self.on_summary_table_change)
        self._setup.cold_changed.connect(self.on_summary_table_change)
        self._setup.dt_changed.connect(self.on_summary_table_change)

    def update_setup_units(self, text: str) -> None:
        if text == 'SI':
            self._setup.units = SIUnits()
        elif text == 'US':
            self._setup.units = USUnits()

    def open_interval_diagram(self) -> None:
        dialog = TemperatureIntervalDiagramDialog(self._setup)
        dialog.exec_()

    def open_cascade_diagram(self) -> None:
        dialog = CascadeDiagramDialog(self._setup)
        dialog.exec_()

    def open_enthalpy_diagram(self) -> None:
        dialog = CompositeEnthalpyDialog(self._setup)
        dialog.exec_()

    def open_network_design(self) -> None:
        current_hsd_name = pathlib.Path(
            self.windowTitle().split('HENSAD - ')[1]
        ).resolve()
        dialog = PinchDesignDialog(self._setup, str(current_hsd_name))
        dialog.exec_()

    def open_eaoc_plot(self) -> None:
        dialog = EAOCDialog(self._setup)
        dialog.exec_()

    def set_input_table_delegates(self, typ: str):
        if typ == 'hot':
            frame = self._setup.hot
            table = self.ui.hotStreamTableView
            delegates = self._hot_delegates
        elif typ == 'cold':
            frame = self._setup.cold
            table = self.ui.coldStreamTableView
            delegates = self._cold_delegates

        SFM = StreamFrameMapper
        for idx, col in enumerate(frame.columns):
            if col == SFM.TIN.name or col == SFM.TOUT.name:
                delegate = TemperatureEditorDelegate()
            elif col == SFM.CP.name or col == SFM.FLOW.name:
                delegate = StreamEditorDelegate()
            elif col == SFM.ID.name:
                delegate = StreamIdDelegate()

            delegates.append(delegate)
            table.setItemDelegateForColumn(idx, delegate)

    def set_film_coef_delegates(self, typ: str):
        if typ == 'hot':
            frame = self._setup.hot_film_coef
            table = self.ui.hotFilmCoefTableView
            delegates = self._hot_delegates
        elif typ == 'cold':
            frame = self._setup.cold_film_coef
            table = self.ui.coldFilmCoefTableView
            delegates = self._cold_delegates

        table.setItemDelegateForColumn(0, FilmCoefficientEditorDelegate())

    def save_file(self):
        current_hsd_name = pathlib.Path(
            self.windowTitle().split('HENSAD - ')[1]
        ).resolve()

        if current_hsd_name.exists():
            self._setup.save(str(current_hsd_name))
        else:
            self.save_file_as()

    def save_file_as(self):
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
            self.setWindowTitle("HENSAD - " + hsd_filepath)
            self._setup.save(str(hsd_filepath))

    def open_file(self):
        dialog_title = "Select the .hsd file to open."
        filetype = "HENSAD files (*.hsd)"
        homedir = pathlib.Path().home()
        hsd_filepath, _ = QFileDialog.getOpenFileName(
            self,
            dialog_title,
            str(homedir),
            filetype
        )

        if hsd_filepath != '':
            self.setWindowTitle("HENSAD - " + hsd_filepath)
            self._setup.load(hsd_filepath)

    def on_add_hot_stream_clicked(self):
        self._setup.add_stream('hot')

    def on_add_cold_stream_clicked(self):
        self._setup.add_stream('cold')

    def on_del_hot_stream_clicked(self):
        table = self.ui.hotStreamTableView
        selection_model = table.selectionModel()

        for index in selection_model.selectedIndexes():
            self._setup.delete_stream(index.row(), 'hot')

        selection_model.clearSelection()

    def on_del_cold_stream_clicked(self):
        table = self.ui.coldStreamTableView
        selection_model = table.selectionModel()

        for index in selection_model.selectedIndexes():
            self._setup.delete_stream(index.row(), 'cold')

        selection_model.clearSelection()

    def on_approach_temp_changed(self):
        self._setup.dt = float(self.ui.dtApproachLineEdit.text())

    def on_summary_table_change(self):
        dt_edit = self.ui.dtApproachLineEdit
        dt_edit.blockSignals(True)
        dt_edit.setText(str(self._setup.dt))
        dt_edit.blockSignals(False)

        # load labels
        pinch_label = self.ui.pinchLabel
        pinch = self._setup.pinch
        if np.isnan(pinch):
            pinch = 'No pinch found'
        pinch_label.setText(str(pinch))

        huq = self._setup.hot_util_req
        cuq = self._setup.cold_util_req
        n_ex = self._setup.min_exchangers

        huq_label = self.ui.hotUtilLabel
        cuq_label = self.ui.coldUtilLabel
        minex_label = self.ui.minExLabel

        huq_label.setText(str(huq))
        cuq_label.setText(str(cuq))
        minex_label.setText(str(n_ex))

        # check if temperatures are set correctly
        hot = self._setup.hot
        cold = self._setup.cold

        SFM = StreamFrameMapper

        hot_ok = (hot[SFM.TIN.name] > hot[SFM.TOUT.name]).all() and \
            (hot[SFM.ID.name].value_counts() == 1).all() and \
            not hot.empty
        cold_ok = (cold[SFM.TIN.name] < cold[SFM.TOUT.name]).all() and \
            (cold[SFM.ID.name].value_counts() == 1).all() and \
            not cold.empty

        all_checks = all([hot_ok, cold_ok])
        has_pinch = pinch != 'No pinch found'

        if all_checks:
            self.ui.tiDiagramPushButton.setEnabled(True)
            self.ui.cascadeDiagramPushButton.setEnabled(True)
        else:
            self.ui.tiDiagramPushButton.setEnabled(False)
            self.ui.cascadeDiagramPushButton.setEnabled(False)

        if all_checks and has_pinch:
            self.ui.tqDiagramPushButton.setEnabled(True)
            self.ui.designToolPushButton.setEnabled(True)
            self.ui.eaocPlotPushButton.setEnabled(True)
        else:
            self.ui.tqDiagramPushButton.setEnabled(False)
            self.ui.designToolPushButton.setEnabled(False)
            self.ui.eaocPlotPushButton.setEnabled(False)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    w = MainWindow()
    w.show()

    sys.excepthook = my_exception_hook

    sys.exit(app.exec_())
