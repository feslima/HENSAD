import json
import pathlib

import numpy as np
import pandas as pd
from PyQt5.QtCore import QObject, pyqtSignal

from hensad import (BaseUnits, FilmCoefficientsFrameMapper,
                    HeatExchangerDesignFrameMapper, HeatFlowFrameMapper,
                    SIUnits, StreamFrameMapper, SummaryFrameMapper, USUnits,
                    calculate_heat_flows, calculate_intervals,
                    calculate_log_mean_diff, calculate_minimum_exchangers,
                    calculate_pinch_utilities, calculate_summary_table,
                    pinch_streams_tables)

EMPTY_SUMMARY = pd.DataFrame(columns=SummaryFrameMapper.columns())
EMPTY_STREAM = pd.DataFrame(columns=StreamFrameMapper.columns())
EMPTY_HEATFLOW = pd.DataFrame(columns=HeatFlowFrameMapper.columns())
EMPTY_EXDES = pd.DataFrame(columns=HeatExchangerDesignFrameMapper.columns())
EMPTY_COEFS = pd.DataFrame(columns=FilmCoefficientsFrameMapper.columns())

STFM = StreamFrameMapper
SFM = SummaryFrameMapper
HFM = HeatFlowFrameMapper
HEDFM = HeatExchangerDesignFrameMapper
FCFM = FilmCoefficientsFrameMapper


class Setup(QObject):
    units_changed = pyqtSignal()
    dt_changed = pyqtSignal()
    hot_changed = pyqtSignal()
    cold_changed = pyqtSignal()

    design_above_changed = pyqtSignal()
    design_below_changed = pyqtSignal()

    hot_coeffs_changed = pyqtSignal()
    cold_coeffs_changed = pyqtSignal()

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
            self._hot = self._hot.astype({STFM.ID.name: object})

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
            self._cold = self._cold.astype({STFM.ID.name: object})

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
    def heat_flow(self) -> pd.DataFrame:
        """Frame containing the heat flow from hot utility into intervals and
        between intervals."""
        if not hasattr(self, '_heat_flow'):
            self._heat_flow = EMPTY_HEATFLOW.copy(deep=True)

        return self._heat_flow

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

    @property
    def design_above(self) -> pd.DataFrame:
        """Heat Exchanger Network design for above the pinch."""
        if not hasattr(self, '_design_above'):
            self._design_above = EMPTY_EXDES.copy(deep=True)

        return self._design_above

    @design_above.setter
    def design_above(self, value: pd.DataFrame) -> None:
        if not isinstance(value, pd.DataFrame):
            raise TypeError("Value has to be a DataFrame.")

        if not np.isin(self.design_above.columns, value.columns).all(axis=None):
            raise ValueError("All column names of DataFrame must be "
                             "specified.")

        if value.isna().any(axis=None):
            raise ValueError("DataFrame cannot contain NaN values.")

        self._design_above = value
        self.design_above_changed.emit()

    @property
    def design_below(self) -> pd.DataFrame:
        """Heat Exchanger Network design for below the pinch."""
        if not hasattr(self, '_design_below'):
            self._design_below = EMPTY_EXDES.copy(deep=True)

        return self._design_below

    @design_below.setter
    def design_below(self, value: pd.DataFrame) -> None:
        if not isinstance(value, pd.DataFrame):
            raise TypeError("Value has to be a DataFrame.")

        if not np.isin(self.design_below.columns, value.columns).all(axis=None):
            raise ValueError("All column names of DataFrame must be "
                             "specified.")

        if value.isna().any(axis=None):
            raise ValueError("DataFrame cannot contain NaN values.")

        self._design_below = value
        self.design_below_changed.emit()

    @property
    def hot_film_coef(self) -> pd.DataFrame:
        """Hot streams film heat transfer coefficients."""
        if not hasattr(self, '_hot_film_coef'):
            self._hot_film_coef = EMPTY_COEFS.copy(deep=True)

        return self._hot_film_coef

    @hot_film_coef.setter
    def hot_film_coef(self, value: pd.DataFrame) -> None:
        if not isinstance(value, pd.DataFrame):
            raise TypeError("Value has to be a DataFrame.")

        if not np.isin(
            self.hot_film_coef.columns,
            value.columns
        ).all(axis=None):
            raise ValueError("All column names of DataFrame must be "
                             "specified.")

        self._hot_film_coef = value
        self.hot_coeffs_changed.emit()

    @property
    def cold_film_coef(self) -> pd.DataFrame:
        """Cold streams film heat transfer coefficients."""
        if not hasattr(self, '_cold_film_coef'):
            self._cold_film_coef = EMPTY_COEFS.copy(deep=True)

        return self._cold_film_coef

    @cold_film_coef.setter
    def cold_film_coef(self, value: pd.DataFrame) -> None:
        if not isinstance(value, pd.DataFrame):
            raise TypeError("Value has to be a DataFrame.")

        if not np.isin(
            self.cold_film_coef.columns,
            value.columns
        ).all(axis=None):
            raise ValueError("All column names of DataFrame must be "
                             "specified.")

        self._cold_film_coef = value
        self.cold_coeffs_changed.emit()

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

            hf = EMPTY_HEATFLOW.copy(deep=True)

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

            # heat flow info
            hf = calculate_heat_flows(summary)

        # set the results
        self._summary = summary

        self._pinch = pinch
        self._hot_util_req = hur
        self._cold_util_req = cur

        self._hot_above = ha
        self._cold_above = ca
        self._hot_below = hb
        self._cold_below = cb

        self._heat_flow = hf

        # minimum number of exchangers
        self._above_min_exchangers = calculate_minimum_exchangers(
            self.hot_above, self.cold_above, 'above'
        )
        self._below_min_exchangers = calculate_minimum_exchangers(
            self.hot_below, self.cold_below, 'below'
        )

    def add_stream(self, typ: str) -> None:
        if typ == 'hot':
            df = self.hot
        elif typ == 'cold':
            df = self.cold

        new_row = {}
        new_stream = "S{:d}".format(len(df) + 1)
        for col in df.columns:
            if col == STFM.ID.name:
                new_row[col] = new_stream
            else:
                new_row[col] = 0.0

        new_film_row = {
            FCFM.ID.name: new_stream,
            FCFM.COEF.name: np.NaN
        }

        if typ == 'hot':
            hot = self.hot.append(new_row, ignore_index=True)
            self.hot = hot

            hot_film = self.hot_film_coef.append(new_film_row,
                                                 ignore_index=True)
            self.hot_film_coef = hot_film

        elif typ == 'cold':
            cold = self.cold.append(new_row, ignore_index=True)
            self.cold = cold

            cold_film = self.cold_film_coef.append(new_film_row,
                                                   ignore_index=True)
            self.cold_film_coef = cold_film

    def delete_stream(self, index: int, typ: str) -> None:
        if typ == 'hot':
            hot = self.hot
            hot = hot.drop(labels=hot.index[index], axis='index')
            hot.reset_index(drop=True, inplace=True)
            self.hot = hot

            hot_film = self.hot_film_coef
            hot_film = hot_film.drop(labels=hot_film.index[index],
                                     axis='index')
            hot_film.reset_index(drop=True, inplace=True)
            self.hot_film_coef = hot_film

        elif typ == 'cold':
            cold = self.cold.drop(labels=self.cold.index[index], axis='index')
            cold.reset_index(drop=True, inplace=True)
            self.cold = cold

            cold_film = self.cold_film_coef
            cold_film = cold_film.drop(labels=cold_film.index[index],
                                       axis='index')
            cold_film.reset_index(drop=True, inplace=True)
            self.cold_film_coef = cold_film

    def add_exchanger(self, des_type: str, ex_id: str, duty: float,
                      interval: str, stream_source: str,
                      stream_dest: str) -> None:
        """Adds a single exchanger on the specified design type (above or
        below the pinch).

        Parameters
        ----------
        des_type : str
            Design type. Valid values are 'abv' or 'blw'.
        ex_id : str
            Exchanger label identifier. Must be unique.
        duty : float
            Heat duty.
        interval : str
            Temperature interval which the exchanger is located.
        stream_source : str
            Heat source (hot) stream ID.
        stream_dest : str
            Heat destination (cold) stream ID.
        """
        # input sanitation
        if des_type == 'abv':
            hot_df = self.hot_above
            cold_df = self.cold_above
            design = self.design_above
        elif des_type == 'blw':
            hot_df = self.hot_below
            cold_df = self.cold_below
            design = self.design_below
        else:
            raise ValueError("Invalid design choice.")

        # check if the input film coefficients are available
        if self.hot_film_coef.empty or self.cold_film_coef.empty or \
            self.hot_film_coef.isna().any(axis=None) or \
                self.cold_film_coef.isna().any(axis=None):
            raise ValueError("Heat transfer film coefficients must be set.")

        # check if exchanger id is unique
        if ex_id in design[HEDFM.ID.name]:
            raise ValueError("Heat exchanger ID must be unique.")

        # check if streams ids (both hot and cold exists)
        if stream_source not in hot_df[STFM.ID.name]:
            raise KeyError("Stream {0} not found.".format(stream_source))

        if stream_dest not in cold_df[STFM.ID.name]:
            raise KeyError("Stream {0} not found.".format(stream_dest))

        # check if the duty is feasible
        hot_stream_info = hot_df.loc[hot_df[STFM.ID.name] == stream_source, :]
        h_tin = hot_stream_info[STFM.TIN.name]
        h_tout = hot_stream_info[STFM.TOUT.name]
        h_cp = hot_stream_info[STFM.CP.name]
        h_mf = hot_stream_info[STFM.FLOW.name]

        cold_stream_info = cold_df.loc[cold_df[STFM.ID.name] == stream_dest, :]
        c_tin = cold_stream_info[STFM.TIN.name]
        c_tout = cold_stream_info[STFM.TOUT.name]
        c_cp = cold_stream_info[STFM.CP.name]
        c_mf = cold_stream_info[STFM.FLOW.name]

        # check duty with stream heat capacities calculate outlet temperatures
        if duty > np.abs((h_mf * h_cp) * (h_tin - h_tout)):
            raise ValueError("The specified heat duty is not feasible for the "
                             "hot stream.")
        else:
            h_tout = h_tin - duty / (h_mf * h_cp)

        if duty > np.abs((c_mf * c_cp) * (c_tout - c_tin)):
            raise ValueError("The specified heat duty is not feasible for the "
                             "cold stream.")
        else:
            c_tout = c_tin + duty / (c_mf * c_cp)

        # log mean correction factor
        f = 0.8

        # log mean temp
        ex_type = 'counter'
        dtln = calculate_log_mean_diff(ex_type, h_tin, h_tout, c_tin, c_tout)

        # heat transfer coefficient
        hot_coef = self.hot_film_coef.loc[
            self.hot_film_coef[FCFM.ID.name] == stream_source,
            FCFM.COEF.name
        ]
        cold_coef = self.cold_film_coef.loc[
            self.cold_film_coef[FCFM.ID.name] == stream_dest,
            FCFM.COEF.name
        ]
        u = 1 / (1 / hot_coef + 1 / cold_coef)

        # exchanger area
        a = duty / (u * dtln * f)

        # store the exchanger data
        new_row = {
            HEDFM.ID.name: ex_id,
            HEDFM.INT.name: interval,
            HEDFM.DUTY.name: duty,
            HEDFM.SOURCE.name: stream_source,
            HEDFM.DEST.name: stream_dest,
            HEDFM.TYPE.name: ex_type,
            HEDFM.DT.name: dtln,
            HEDFM.U.name: u,
            HEDFM.F.name: f,
            HEDFM.A.name: a
        }

        design = design.append(new_row, ignore_index=True)

    def load(self, filename: str) -> None:
        check_file_exists(filename)

        with open(filename, 'r') as fp:
            hsd = json.load(fp)
        hot = pd.DataFrame(hsd['hot'])
        hot = hot.astype(
            {key: float if key != STFM.ID.name else object
             for key in STFM.columns()}
        )
        hot.index = hot.index.astype(int)

        cold = pd.DataFrame(hsd['cold'])
        cold = cold.astype(
            {key: float if key != STFM.ID.name else object
             for key in STFM.columns()}
        )
        cold.index = cold.index.astype(int)

        hot_film = pd.DataFrame(hsd['hot_film'])
        hot_film = hot_film.astype(
            {key: float if key != FCFM.ID.name else object
             for key in FCFM.columns()}
        )
        hot_film.index = hot_film.index.astype(int)

        cold_film = pd.DataFrame(hsd['cold_film'])
        cold_film = cold_film.astype(
            {key: float if key != FCFM.ID.name else object
             for key in FCFM.columns()}
        )
        cold_film.index = cold_film.index.astype(int)

        self.blockSignals(True)

        self.hot = hot
        self.cold = cold

        self.blockSignals(False)

        self.dt = hsd['dt']

        self.hot_film_coef = hot_film
        self.cold_film_coef = cold_film

    def save(self, filename: str) -> None:
        dump = {
            'dt': self.dt,
            'hot': self.hot.to_dict(),
            'cold': self.cold.to_dict(),
            'hot_film': self.hot_film_coef.to_dict(),
            'cold_film': self.cold_film_coef.to_dict()
        }

        with open(filename, 'w') as fp:
            json.dump(dump, fp, indent=4)


def check_file_exists(filename: str) -> None:
    filepath = pathlib.Path(filename).resolve()

    if not filepath.exists() or not filepath.is_file():
        raise FileNotFoundError("Invalid .hsd file specified.")
