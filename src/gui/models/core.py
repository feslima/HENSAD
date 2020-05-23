import json
import pathlib

import numpy as np
import pandas as pd
from PyQt5.QtCore import QObject, pyqtSignal

from hensad import (
    BaseUnits, SIUnits, StreamFrameMapper, SummaryFrameMapper, USUnits,
    calculate_intervals, calculate_minimum_exchangers,
    calculate_pinch_utilities, calculate_summary_table, pinch_streams_tables)

EMPTY_SUMMARY = pd.DataFrame(columns=SummaryFrameMapper.columns())
EMPTY_STREAM = pd.DataFrame(columns=StreamFrameMapper.columns())

STFM = StreamFrameMapper


class Setup(QObject):
    units_changed = pyqtSignal()
    dt_changed = pyqtSignal()
    hot_changed = pyqtSignal()
    cold_changed = pyqtSignal()

    @property
    def units(self) -> BaseUnits:
        """Unit set."""
        return self._units

    @units.setter
    def units(self, value: BaseUnits) -> None:
        if not isinstance(value, BaseUnits):
            raise TypeError("Unit system must be a valid set.")

        self._units = value
        self.units_changed.emit()

    @property
    def dt(self) -> float:
        """Minimum approach temperature."""
        if not hasattr(self, '_dt'):
            self._dt = np.NaN
        return self._dt

    @dt.setter
    def dt(self, value: float) -> None:
        if not isinstance(value, float):
            raise TypeError("Minimum temperature value has to be a float.")
        self._dt = value
        self.dt_changed.emit()

    @property
    def hot(self) -> pd.DataFrame:
        """DataFrame containing the hot side streams info."""
        if not hasattr(self, '_hot'):
            self._hot = EMPTY_STREAM.copy(deep=True)

        return self._hot

    @hot.setter
    def hot(self, value: pd.DataFrame) -> None:
        if not isinstance(value, pd.DataFrame):
            raise TypeError("Value has to be a DataFrame.")

        if not np.isin(self.hot.columns, value.columns).all(axis=None):
            raise ValueError("All column names of DataFrame must be "
                             "specified.")

        if value.isna().any(axis=None):
            raise ValueError("DataFrame cannot contain NaN values.")

        self._hot = value
        self.hot_changed.emit()

    @property
    def cold(self) -> pd.DataFrame:
        """DataFrame containing the cold side streams info."""
        if not hasattr(self, '_cold'):
            self._cold = EMPTY_STREAM.copy(deep=True)

        return self._cold

    @cold.setter
    def cold(self, value: pd.DataFrame) -> None:
        if not isinstance(value, pd.DataFrame):
            raise TypeError("Value has to be a DataFrame.")

        if not np.isin(self.cold.columns, value.columns).all(axis=None):
            raise ValueError("All column names of DataFrame must be "
                             "specified.")

        if value.isna().any(axis=None):
            raise ValueError("DataFrame cannot contain NaN values.")

        self._cold = value
        self.cold_changed.emit()

    @property
    def hot_interval(self) -> pd.Series:
        """Unique temperature interval values for the hot side. Values are
        sorted from largest to smallest."""
        if not hasattr(self, '_hot_interval'):
            self._hot_interval = pd.Series(np.nan)

        return self._hot_interval

    @property
    def summary(self) -> pd.DataFrame:
        """Interval summary for the current values of hot, cold streams and dt.
        """
        if not hasattr(self, '_summary'):
            self._summary = EMPTY_SUMMARY.copy(deep=True)
        return self._summary

    @property
    def pinch(self) -> float:
        """Pinch temperature (Hot side)."""
        return self._pinch

    @property
    def hot_util_req(self) -> float:
        """Hot utility heat requirement."""
        return self._hot_util_req

    @property
    def cold_util_req(self) -> float:
        """Cold utility heat requirement."""
        return self._cold_util_req

    @property
    def hot_above(self) -> pd.DataFrame:
        """Hot side streams information table above the pinch."""
        if not hasattr(self, '_hot_above'):
            self._hot_above = EMPTY_STREAM.copy(deep=True)
        return self._hot_above

    @property
    def cold_above(self) -> pd.DataFrame:
        """Cold side streams information table above the pinch."""
        if not hasattr(self, '_cold_above'):
            self._cold_above = EMPTY_STREAM.copy(deep=True)
        return self._cold_above

    @property
    def hot_below(self) -> pd.DataFrame:
        """Hot side streams information table below the pinch."""
        if not hasattr(self, '_hot_below'):
            self._hot_below = EMPTY_STREAM.copy(deep=True)
        return self._hot_below

    @property
    def cold_below(self) -> pd.DataFrame:
        """Cold side streams information table below the pinch."""
        if not hasattr(self, '_cold_below'):
            self._cold_below = EMPTY_STREAM.copy(deep=True)
        return self._cold_below

    @property
    def above_min_exchangers(self) -> int:
        """Minimum number of heat exchangers above the pinch."""
        return self._above_min_exchangers

    @property
    def below_min_exchangers(self) -> int:
        """Minimum number of heat exchangers below the pinch."""
        return self._below_min_exchangers

    @property
    def min_exchangers(self) -> int:
        """Minimum number of heat exchangers."""
        return self.above_min_exchangers + self.below_min_exchangers

    def __init__(self, units: str = 'SI'):
        super().__init__(parent=None)

        if units == 'SI':
            self.units = SIUnits()
        elif units == 'US':
            self.units = USUnits()
        else:
            raise ValueError("Invalid unit system.")

        # update the summary when the following changes occur:
        self.hot_changed.connect(self._update_summary)
        self.cold_changed.connect(self._update_summary)
        self.dt_changed.connect(self._update_summary)

    def _update_summary(self):
        try:
            summary = calculate_summary_table(self.hot, self.cold, self.dt)
        except ValueError as e:
            # either the hot or cold frames are empty

            # set pinch and utilities (no pinch)
            pinch, hur, cur = (np.NaN, 0.0, 0.0)

            # clear the summary and pinch stream infos
            summary = EMPTY_SUMMARY.copy(deep=True)
            ha = EMPTY_STREAM.copy(deep=True)
            ca = EMPTY_STREAM.copy(deep=True)

            hb = EMPTY_STREAM.copy(deep=True)
            cb = EMPTY_STREAM.copy(deep=True)

        else:
            # calculation was successful
            # update the temperature interval values
            hit, _ = calculate_intervals(self.hot, self.cold, self.dt)
            self._hot_interval = hit

            # set pinch and utilities
            pinch, hur, cur = calculate_pinch_utilities(summary)

            # pinch stream infos
            ha, ca, hb, cb = pinch_streams_tables(self.hot, self.cold,
                                                  self.dt, pinch)

        # set the results
        self._summary = summary

        self._pinch = pinch
        self._hot_util_req = hur
        self._cold_util_req = cur

        self._hot_above = ha
        self._cold_above = ca
        self._hot_below = hb
        self._cold_below = cb

        # minimum number of exchangers
        self._above_min_exchangers = calculate_minimum_exchangers(
            self.hot_above, self.cold_above, 'above'
        )
        self._below_min_exchangers = calculate_minimum_exchangers(
            self.hot_below, self.cold_below, 'below'
        )

    def add_stream(self, typ: str) -> None:
        new_row = pd.Series({col: 0.0 for col in self.hot.columns})

        if typ == 'hot':
            hot = self.hot.append(new_row, ignore_index=True)
            self.hot = hot

        elif typ == 'cold':
            cold = self.cold.append(new_row, ignore_index=True)
            self.cold = cold

    def delete_stream(self, index: int, typ: str) -> None:
        if typ == 'hot':
            hot = self.hot.drop(labels=self.hot.index[index], axis='index')
            hot.reset_index(drop=True, inplace=True)
            self.hot = hot
        elif typ == 'cold':
            cold = self.cold.drop(labels=self.cold.index[index], axis='index')
            cold.reset_index(drop=True, inplace=True)
            self.cold = cold

    def load(self, filename: str) -> None:
        check_file_exists(filename)

        with open(filename, 'r') as fp:
            hsd = json.load(fp)
        hot = pd.DataFrame(hsd['hot'])
        hot = hot.astype({key: float for key in STFM.columns()})
        hot.index = hot.index.astype(int)

        cold = pd.DataFrame(hsd['cold'])
        cold = cold.astype({key: float for key in STFM.columns()})
        cold.index = cold.index.astype(int)

        self.blockSignals(True)

        self.hot = hot
        self.cold = cold

        self.blockSignals(False)

        self.dt = hsd['dt']

    def save(self, filename: str) -> None:
        dump = {
            'dt': self.dt,
            'hot': self.hot.to_dict(),
            'cold': self.cold.to_dict(),
        }

        with open(filename, 'w') as fp:
            json.dump(dump, fp, indent=4)


def check_file_exists(filename: str) -> None:
    filepath = pathlib.Path(filename).resolve()

    if not filepath.exists() or not filepath.is_file():
        raise FileNotFoundError("Invalid .hsd file specified.")
