import json
import pathlib

import pandas as pd
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import (QApplication, QFileDialog, QHeaderView,
                             QMainWindow, QTableView)

from gui.models.core import Setup, StreamFrameMapper
from gui.models.input_streams import (StreamEditorDelegate,
                                      StreamInputTableModel,
                                      TemperatureEditorDelegate)
from gui.models.summary_table import SummaryModel
from gui.views.py.mainwindow import Ui_MainWindow

DEFAULT_DT = 10


class MinTempApproachValidator(QIntValidator):
    def fixup(self, inp: str):
        if inp == '':
            inp = str(DEFAULT_DT)
        # return super().fixup(inp)
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

        cold_table = self.ui.coldStreamTableView
        cold_model = StreamInputTableModel(self._setup, 'cold', cold_table)
        cold_table.setModel(cold_model)
        self._cold_delegates = []

        cold_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.set_input_table_delegates('cold')

        summary_table = self.ui.summaryTableView
        summary_model = SummaryModel(self._setup, summary_table)
        summary_table.setModel(summary_model)

        summary_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        # DT approach editor
        # TODO: color behavior of input value
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

        self._setup.hot_changed.connect(self.on_summary_table_change)
        self._setup.cold_changed.connect(self.on_summary_table_change)
        self._setup.dt_changed.connect(self.on_summary_table_change)

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

            delegates.append(delegate)
            table.setItemDelegateForColumn(idx, delegate)

    def save_file(self):
        current_hsd_name = pathlib.Path(
            self.windowTitle().split('HENSAD - ')[1]
        ).resolve()

        if current_hsd_name.exists():
            dump_to_hsd(
                str(current_hsd_name),
                self._setup.hot,
                self._setup.cold
            )
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
            dump_to_hsd(
                hsd_filepath,
                self._setup.hot,
                self._setup.cold
            )

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
            hot, cold = read_from_hsd(hsd_filepath)
            self._setup.hot = hot
            self._setup.cold = cold

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
        # check if temperatures are set correctly
        hot = self._setup.hot
        cold = self._setup.cold

        SFM = StreamFrameMapper

        hot_ok = (hot[SFM.TIN.name] > hot[SFM.TOUT.name]).all()
        cold_ok = (cold[SFM.TIN.name] < cold[SFM.TOUT.name]).all()

        if hot_ok and cold_ok:
            self.ui.tiDiagramPushButton.setEnabled(True)
        else:
            self.ui.tiDiagramPushButton.setEnabled(False)


def dump_to_hsd(filename: str, hot: pd.DataFrame, cold: pd.DataFrame):
    dump = {
        'hot': hot.to_dict(),
        'cold': cold.to_dict(),
    }

    with open(filename, 'w') as fp:
        json.dump(dump, fp, indent=4)


def read_from_hsd(filename: str):
    with open(filename, 'r') as fp:
        hsd = json.load(fp)
    hot = pd.DataFrame(hsd['hot'])
    hot = hot.astype(
        {key: float for key in StreamFrameMapper.columns()}
    )
    hot.index = hot.index.astype(int)

    cold = pd.DataFrame(hsd['cold'])
    cold = cold.astype(
        {key: float for key in StreamFrameMapper.columns()}
    )
    cold.index = cold.index.astype(int)
    return hot, cold


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    w = MainWindow()
    w.show()

    sys.exit(app.exec_())
