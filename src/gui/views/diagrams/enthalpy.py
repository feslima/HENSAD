import pandas as pd
from matplotlib.backends.backend_qt5agg import (FigureCanvasQTAgg,
                                                NavigationToolbar2QT)
from matplotlib.figure import Figure
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog, QSlider, QVBoxLayout

from gui.models.core import HFM, SFM, STFM, Setup


class CompositeEnthalpyDialog(QDialog):
    def __init__(self, setup: Setup):
        super().__init__()
        self.setWindowFlags(Qt.Window)
        self.setWindowTitle("Composite Enthalpy Diagram")

        self._setup = setup

        self._figure = Figure()
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._plt_toolbar = NavigationToolbar2QT(self._canvas, self)

        slider = QSlider(self)
        self._slider = slider
        slider.setValue(self._setup.dt)
        slider.setMinimum(5)
        slider.setMaximum(30)
        slider.setSingleStep(2)
        slider.setOrientation(Qt.Horizontal)
        slider.sliderReleased.connect(self._on_dt_changed)

        setup.dt_changed.connect(self._plot_graph)

        layout = QVBoxLayout()
        layout.addWidget(slider)
        layout.addWidget(self._canvas)
        layout.addWidget(self._plt_toolbar)
        self.setLayout(layout)

        self._plot_graph()

    def _on_dt_changed(self):
        dt_value = self._slider.value()
        self._setup.dt = float(dt_value)

    def _plot_graph(self) -> None:
        self._figure.clear()
        ax = self._figure.add_subplot(111)
        summary = self._setup.summary

        hTQ = pd.DataFrame(columns=['Q', 'T'], dtype=float)
        cTQ = pd.DataFrame(columns=['Q', 'T'], dtype=float)

        hs = summary.sort_values(
            by=SFM.TIN.name, ascending=True, ignore_index=True
        )
        cs = hs.copy(deep=True)

        hcumq = 0.0
        ccumq = self._setup.cold_util_req
        hot = self._setup.hot
        cold = self._setup.cold
        dt = self._setup.dt
        for i in range(hs.shape[0]):
            htout = hs.at[i, SFM.TOUT.name]
            htin = hs.at[i, SFM.TIN.name]
            ctout = htout - dt
            ctin = htin - dt

            hTQ.at[i, 'T'] = htout
            hTQ.at[i + 1, 'T'] = htin
            cTQ.at[i, 'T'] = ctout
            cTQ.at[i + 1, 'T'] = ctin

            hTQ.at[i, 'Q'] = hcumq
            cTQ.at[i, 'Q'] = ccumq

            for s in hs.at[i, SFM.HOTSTRIDX.name]:
                hcumq += hot.at[s, STFM.FLOW.name] * \
                    hot.at[s, STFM.CP.name] * (htin - htout)

            for s in hs.at[i, SFM.COLDSTRIDX.name]:
                ccumq += cold.at[s, STFM.FLOW.name] * \
                    cold.at[s, STFM.CP.name] * (ctin - ctout)

            hTQ.at[i + 1, 'Q'] = hcumq
            cTQ.at[i + 1, 'Q'] = ccumq

        ax.plot(hTQ['Q'], hTQ['T'], 'r', label='Hot')
        ax.plot(cTQ['Q'], cTQ['T'], 'b', label='Cold')
        ax.legend()
        ax.set_xlabel('Q ({0})'.format(self._setup.units.power))
        ax.set_ylabel('T ({0})'.format(self._setup.units.temperature))
        ax.set_title('T-Q Composite diagram\n$\Delta T$ = {0:.6g}{1}'.format(
            dt, self._setup.units.temperature
        ))
        ax.grid(which='both')
        self._figure.canvas.draw()


if __name__ == "__main__":
    import sys
    import pathlib

    hsd_filepath = pathlib.Path().resolve() / "tests" / "hsdtest.hsd"

    setup = Setup()
    setup.load(str(hsd_filepath))

    app = QApplication(sys.argv)

    w = CompositeEnthalpyDialog(setup)
    w.show()

    sys.exit(app.exec_())
