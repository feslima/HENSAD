import numpy as np
import pandas as pd
from matplotlib.backends.backend_qt5agg import (FigureCanvasQTAgg,
                                                NavigationToolbar2QT)
from matplotlib.figure import Figure
from PyQt5.QtCore import QAbstractTableModel, Qt
from PyQt5.QtWidgets import (QApplication, QDialog, QSlider, QTableView,
                             QVBoxLayout)

from gui.models.core import Setup
from hensad import ArrangementType, ExchangerType, MaterialType, calculate_eaoc


class EAOCDialog(QDialog):
    def __init__(self, setup: Setup):
        super().__init__()
        self.setWindowFlags(Qt.Window)
        self.setWindowTitle("EAOC - DT plot")

        self._setup = setup

        self._figure = Figure()
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._plt_toolbar = NavigationToolbar2QT(self._canvas, self)

        layout = QVBoxLayout()
        layout.addWidget(self._canvas)
        layout.addWidget(self._plt_toolbar)
        self.setLayout(layout)

        # self._plot_graph()

    def _plot_graph(self) -> None:
        hot = self._setup.hot
        cold = self._setup.cold
        hot_coef = self._setup.hot_film_coef
        cold_coef = self._setup.cold_film_coef

        new_rows = []
        DTMIN = 5
        DTMAX = 55
        for dt in np.arange(DTMIN, DTMAX + 1, dtype=float):
            eaoc, netarea, huq, cuq, n_ex = calculate_eaoc(
                hot, cold, dt, hot_coef, cold_coef,
                ExchangerType.FLOATING_HEAD,
                ArrangementType.SHELL_TUBE,
                MaterialType.CS, MaterialType.CS,
                1.0
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

        self._figure.clear()
        ax = self._figure.add_subplot(111)
        ax.plot(df['dt'], df['eaoc'], color='b')
        ax.set_xlabel('$\Delta T$')
        ax.set_ylabel('EAOC ($/y)')
        ax.grid(which='both')

        self._figure.canvas.draw()


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
