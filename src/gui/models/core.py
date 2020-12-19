import json
import pathlib
from typing import List

import numpy as np
import pandas as pd
from PyQt5.QtCore import QObject, pyqtSignal

from hensad import (COST_DATA, MATERIAL_DATA, ArrangementType, BaseUnits,
                    ExchangerType, FilmCoefficientsFrameMapper,
                    HeatExchangerDesignFrameMapper, HeatFlowFrameMapper,
                    MaterialType, SegmentsFrameMapper, SIUnits,
                    StreamFilmCoefficientFrameMapper, StreamFrameMapper,
                    SummaryFrameMapper, USUnits, calculate_bare_module_cost,
                    calculate_composite_enthalpy, calculate_exchanger_area,
                    calculate_heat_flows, calculate_intervals,
                    calculate_log_mean_diff, calculate_minimum_exchangers,
                    calculate_number_of_shells, calculate_pinch_utilities,
                    calculate_segments_data, calculate_summary_table,
                    pinch_streams_tables)

STFM = StreamFrameMapper
SFM = SummaryFrameMapper
HFM = HeatFlowFrameMapper
HEDFM = HeatExchangerDesignFrameMapper
FCFM = FilmCoefficientsFrameMapper
STFCFM = StreamFilmCoefficientFrameMapper
SEGFM = SegmentsFrameMapper

HEDFM_STR_COLS = [
    HEDFM.ID.name,
    HEDFM.INT.name,
    HEDFM.SOURCE.name,
    HEDFM.DEST.name,
    HEDFM.TYPE.name,
    HEDFM.ARRANGEMENT.name,
    HEDFM.SHELL.name,
    HEDFM.TUBE.name
]

EMPTY_SUMMARY = pd.DataFrame(columns=SFM.columns())
EMPTY_STREAM = pd.DataFrame(columns=STFM.columns())
EMPTY_COMPOSITE = pd.DataFrame(columns=['Q', 'T'], dtype=float)
EMPTY_SEGMENT = pd.DataFrame(columns=SEGFM.columns())
EMPTY_HEATFLOW = pd.DataFrame(columns=HFM.columns())
EMPTY_EXDES = pd.DataFrame(columns=HEDFM.columns())
EMPTY_COEFS = pd.DataFrame(columns=FCFM.columns())
EMPTY_STREAM_COEFS = pd.DataFrame(columns=STFCFM.columns())


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
    def hot_composite_data(self) -> pd.DataFrame:
        """Hot streams composite enthalpy curve data."""
        return self._hot_composite_data

    @property
    def cold_composite_data(self) -> pd.DataFrame:
        """Cold streams composite enthalpy curve data."""
        return self._cold_composite_data

    @property
    def composite_segments_data(self) -> pd.DataFrame:
        """Composite enthalpy segment data."""
        return self._composite_segments_data

    @property
    def area_network(self) -> float:
        """Heat exchanger network total area estimate"""
        return self._area_network

    @property
    def hot_above(self) -> pd.DataFrame:
        """Hot side streams information table above the pinch."""
        if not hasattr(self, '_hot_above'):
            self._hot_above = EMPTY_STREAM_COEFS.copy(deep=True)
        return self._hot_above

    @property
    def cold_above(self) -> pd.DataFrame:
        """Cold side streams information table above the pinch."""
        if not hasattr(self, '_cold_above'):
            self._cold_above = EMPTY_STREAM_COEFS.copy(deep=True)
        return self._cold_above

    @property
    def hot_below(self) -> pd.DataFrame:
        """Hot side streams information table below the pinch."""
        if not hasattr(self, '_hot_below'):
            self._hot_below = EMPTY_STREAM_COEFS.copy(deep=True)
        return self._hot_below

    @property
    def cold_below(self) -> pd.DataFrame:
        """Cold side streams information table below the pinch."""
        if not hasattr(self, '_cold_below'):
            self._cold_below = EMPTY_STREAM_COEFS.copy(deep=True)
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

        # update the ID from the input table
        value.loc[:, FCFM.ID.name] = self.hot.loc[:, STFM.ID.name]

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

        # update the ID from the input table
        value.loc[:, FCFM.ID.name] = self.cold.loc[:, STFM.ID.name]

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

            # composite enthalpy curves
            hTQ = EMPTY_COMPOSITE.copy(deep=True)
            cTQ = EMPTY_COMPOSITE.copy(deep=True)
            segments = EMPTY_SEGMENT.copy(deep=True)

            # network area
            area_network = np.NaN

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

            # composite enthalpy curves
            hTQ, cTQ = calculate_composite_enthalpy(
                self.hot, self.cold, self.dt,
                hur, cur, self.hot_film_coef, self.cold_film_coef,
                summary
            )

            segments = calculate_segments_data(
                self.hot, self.cold, self.dt,
                hTQ, cTQ, self.hot_film_coef, self.cold_film_coef,
                summary
            )

            # network area
            area_network = (segments[SEGFM.SUM_QH.name]
                            / (segments[SEGFM.DTLN.name] * 0.8)).sum()

            # pinch stream infos
            ha, ca, hb, cb = pinch_streams_tables(self.hot, self.cold,
                                                  self.dt, pinch,
                                                  self.hot_film_coef,
                                                  self.cold_film_coef)

            # heat flow info
            hf = calculate_heat_flows(summary)

        # set the results
        self._summary = summary

        self._pinch = pinch
        self._hot_util_req = hur
        self._cold_util_req = cur

        self._hot_composite_data = hTQ
        self._cold_composite_data = cTQ
        self._composite_segments_data = segments

        self._area_network = area_network

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

        # reset the exchangers designs
        self._design_above = EMPTY_EXDES.copy(deep=True)
        self._design_below = EMPTY_EXDES.copy(deep=True)

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

    def split_stream(self, des_type: str, stream_type: str, stream_id: str,
                     flowrates: List[float]) -> None:
        if des_type == 'abv':
            if stream_type == 'hot':
                streams_df = self.hot_above
            else:
                streams_df = self.cold_above

        else:
            if stream_type == 'hot':
                streams_df = self.hot_below
            else:
                streams_df = self.cold_below

        if stream_id not in streams_df[STFCFM.ID.name].values:
            raise KeyError("Stream ID '{0}' not found.")

        flowrates = np.array(flowrates).astype(float)

        streams_df = streams_df.set_index(STFCFM.ID.name)
        stream = streams_df.loc[stream_id, :]
        flow = stream[STFCFM.FLOW.name]
        sum_flow = flowrates.sum()
        if sum_flow != flow:
            raise ValueError("Sum of specified flowrates must be equal to the "
                             "total flowrate.")
        new_streams = []
        for i, flow in enumerate(flowrates):
            new_str = stream.copy(deep=True).rename()
            new_stream_id = stream_id + '_' + chr(ord('A') + i)
            new_str[STFCFM.ID.name] = new_stream_id
            new_str[STFCFM.FLOW.name] = flow
            new_streams.append(new_str)

        # delete the stream pre split
        streams_df = streams_df.drop(labels=stream_id).reset_index()

        # generate the new splits
        new_streams = pd.concat(
            new_streams, axis='columns', ignore_index=True
        ).transpose()[STFCFM.columns()]

        # concatenate new streams into the current df
        new_streams = pd.concat(
            [streams_df, new_streams], axis='index', ignore_index=True
        )

        # convert the columns data types
        new_streams = new_streams.astype(
            {key: float if key != STFCFM.ID.name else object
             for key in STFCFM.columns()}
        )

        if des_type == 'abv':
            if stream_type == 'hot':
                self._hot_above = new_streams
            else:
                self._cold_above = new_streams

        else:
            if stream_type == 'hot':
                self._hot_below = new_streams
            else:
                self._cold_below = new_streams

        # reset the exchangers designs
        self._design_above = EMPTY_EXDES.copy(deep=True)
        self._design_below = EMPTY_EXDES.copy(deep=True)

    def add_exchanger(self, des_type: str, ex_id: str, duty: float,
                      interval: str, stream_source: str,
                      stream_dest: str, ex_type: ExchangerType,
                      arrangement: ArrangementType,
                      shell_mat: MaterialType, tube_mat: MaterialType,
                      pressure: float, factor: float) -> None:
        """Adds a single process exchanger on the specified design type
        (above or below the pinch).

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
        ex_type : ExchangerType
            Type of heat exchanger (See ExchangerType enumerator for options).
        arrangement : ArrangementType
            Type of tube arranagement (See ArrangementType enumerator).
        shell_mat : MaterialType
            Type of material of the exchanger shell side.
        tube_mat : MaterialType
            Type of material of the exchanger tube side.
        pressure : float
            Heat exchanger operating pressure.
        factor : float
            Correction factor.
        """
        # input sanitation
        if des_type == 'abv':
            hot_df = self.hot_above
            cold_df = self.cold_above
            design = self.design_above
            allowed_ex = self.above_min_exchangers
        elif des_type == 'blw':
            hot_df = self.hot_below
            cold_df = self.cold_below
            design = self.design_below
            allowed_ex = self.below_min_exchangers
        else:
            raise ValueError("Invalid design choice.")

        if len(design) >= allowed_ex:
            raise ValueError(
                "Maximum number of exchangers is {0}".format(allowed_ex)
            )

        # check if the input film coefficients are available
        if self.hot_film_coef.empty or self.cold_film_coef.empty or \
            self.hot_film_coef.isna().any(axis=None) or \
                self.cold_film_coef.isna().any(axis=None):
            raise ValueError("Heat transfer film coefficients must be set.")

        # check if exchanger id is unique
        if ex_id in design[HEDFM.ID.name].values:
            raise ValueError("Heat exchanger ID must be unique.")

        # check if streams ids (both hot and cold exists)
        if stream_source not in hot_df[STFM.ID.name].values:
            raise KeyError("Stream {0} not found.".format(stream_source))

        if stream_dest not in cold_df[STFM.ID.name].values:
            raise KeyError("Stream {0} not found.".format(stream_dest))

        hot_stream_info = hot_df.loc[hot_df[STFM.ID.name] == stream_source, :]
        cold_stream_info = cold_df.loc[cold_df[STFM.ID.name] == stream_dest, :]

        h_cp = hot_stream_info[STFM.CP.name].item()
        h_mf = hot_stream_info[STFM.FLOW.name].item()

        c_cp = cold_stream_info[STFM.CP.name].item()
        c_mf = cold_stream_info[STFM.FLOW.name].item()

        # heat transfer coefficient
        hot_coef = hot_df.loc[
            hot_df[STFCFM.ID.name] == stream_source,
            STFCFM.COEF.name
        ].item()
        cold_coef = cold_df.loc[
            cold_df[STFCFM.ID.name] == stream_dest,
            STFCFM.COEF.name
        ].item()

        if des_type == 'abv':
            # design above: calculate h_tin and c_tout
            h_tin = hot_stream_info[STFM.TIN.name].item()

            if stream_source in design[HEDFM.SOURCE.name].values:
                h_tout = design.loc[
                    design[HEDFM.SOURCE.name] == stream_source,
                    HEDFM.HOT_IN.name
                ].max()
            else:
                h_tout = hot_stream_info[STFM.TOUT.name].item()

            c_tout = cold_stream_info[STFM.TOUT.name].item()

            if stream_dest in design[HEDFM.DEST.name].values:
                c_tin = design.loc[
                    design[HEDFM.DEST.name] == stream_dest,
                    HEDFM.COLD_OUT.name
                ].max()
            else:
                c_tin = cold_stream_info[STFM.TIN.name].item()

        else:
            # design below: calculate h_tout and c_tin
            h_tout = hot_stream_info[STFM.TOUT.name].item()

            if stream_source in design[HEDFM.SOURCE.name].values:
                h_tin = design.loc[
                    design[HEDFM.SOURCE.name] == stream_source,
                    HEDFM.HOT_OUT.name
                ].max()
            else:
                h_tin = hot_stream_info[STFM.TIN.name].item()

            c_tin = cold_stream_info[STFM.TIN.name].item()

            if stream_dest in design[HEDFM.DEST.name].values:
                c_tout = design.loc[
                    design[HEDFM.DEST.name] == stream_dest,
                    HEDFM.COLD_IN.name
                ].max()
            else:
                c_tout = cold_stream_info[STFM.TOUT.name].item()

        # check duty with stream heat capacities calculate outlet temperatures
        if duty > np.abs((h_mf * h_cp) * (h_tin - h_tout)).item():
            raise ValueError("The specified heat duty is not feasible for the "
                             "hot stream.")
        else:
            if des_type == 'abv':
                h_tin = h_tout + duty / (h_mf * h_cp)
            else:
                h_tout = h_tin - duty / (h_mf * h_cp)

        if duty > np.abs((c_mf * c_cp) * (c_tout - c_tin)).item():
            raise ValueError("The specified heat duty is not feasible for the "
                             "cold stream.")
        else:
            if des_type == 'abv':
                c_tout = c_tin + duty / (c_mf * c_cp)
            else:
                c_tin = c_tout - duty / (c_mf * c_cp)

        # log mean temp
        dtln = calculate_log_mean_diff('counter', h_tin, h_tout, c_tin, c_tout)

        # check if the calculated log mean violates the minimun approach
        if dtln < self.dt:
            err_msg = ("The duty and stream combinations violate the minimum "
                       "approach temperature.\n"
                       "Calculated log mean = {0}.\n"
                       "Minimum approach = {1}").format(dtln, self.dt)
            raise ValueError(err_msg)

        # log mean correction factor
        f = factor

        # area and overall heat coefficient
        a, u = calculate_exchanger_area(duty, dtln, hot_coef, cold_coef, f)

        # exchanger costs
        cbm = calculate_bare_module_cost(ex_type, arrangement, shell_mat,
                                         tube_mat, a, pressure)

        # number of shells
        h_str = {
            STFM.ID.name: stream_source,
            STFM.FLOW.name: h_mf,
            STFM.CP.name: h_cp,
            STFM.TIN.name: h_tin,
            STFM.TOUT.name: h_tout
        }
        c_str = {
            STFM.ID.name: stream_dest,
            STFM.FLOW.name: c_mf,
            STFM.CP.name: c_cp,
            STFM.TIN.name: c_tin,
            STFM.TOUT.name: c_tout
        }
        n_shells = calculate_number_of_shells(h_str, c_str)

        # store the exchanger data
        new_row = {
            HEDFM.ID.name: ex_id,
            HEDFM.INT.name: interval,
            HEDFM.DUTY.name: duty,
            HEDFM.COST.name: cbm,
            HEDFM.TYPE.name: ex_type.value,
            HEDFM.ARRANGEMENT.name: arrangement.value,
            HEDFM.SHELL.name: shell_mat.value,
            HEDFM.TUBE.name: tube_mat.value,
            HEDFM.SOURCE.name: stream_source,
            HEDFM.DEST.name: stream_dest,
            HEDFM.HOT_IN.name: h_tin,
            HEDFM.HOT_OUT.name: h_tout,
            HEDFM.COLD_IN.name: c_tin,
            HEDFM.COLD_OUT.name: c_tout,
            HEDFM.DT.name: dtln,
            HEDFM.U.name: u,
            HEDFM.F.name: f,
            HEDFM.A.name: a,
            HEDFM.NSHELL.name: n_shells
        }

        design = design.append(new_row, ignore_index=True)
        if des_type == 'abv':
            self.design_above = design
        else:
            self.design_below = design

    def add_utility_exchanger(self, des_type: str, ex_id: str, duty: float,
                              interval: str, utility_type: str,
                              stream_id: str, ut_in: float, ut_out: float,
                              ut_coef: float, ex_type: ExchangerType,
                              arrangement: ArrangementType,
                              shell_mat: MaterialType, tube_mat: MaterialType,
                              pressure: float, factor: float) -> None:
        # input sanitation
        if des_type == 'abv':
            hot_df = self.hot_above
            cold_df = self.cold_above
            design = self.design_above
            allowed_ex = self.above_min_exchangers
        elif des_type == 'blw':
            hot_df = self.hot_below
            cold_df = self.cold_below
            design = self.design_below
            allowed_ex = self.below_min_exchangers
        else:
            raise ValueError("Invalid design choice.")

        if len(design) >= allowed_ex:
            raise ValueError(
                "Maximum number of exchangers is {0}".format(allowed_ex)
            )

        # check if the input film coefficients are available
        if self.hot_film_coef.empty or self.cold_film_coef.empty or \
            self.hot_film_coef.isna().any(axis=None) or \
                self.cold_film_coef.isna().any(axis=None):
            raise ValueError("Heat transfer film coefficients must be set.")

        # check if exchanger id is unique
        if ex_id in design[HEDFM.ID.name].values:
            raise ValueError("Heat exchanger ID must be unique.")

        if utility_type == 'hot':
            if stream_id not in cold_df[STFM.ID.name].values:
                raise KeyError("Stream {0} not found.".format(stream_id))
            else:
                stream_info = cold_df.loc[
                    cold_df[STFM.ID.name] == stream_id, :
                ]
                coef = cold_df.loc[
                    cold_df[STFCFM.ID.name] == stream_id,
                    STFCFM.COEF.name
                ].item()

                stream_source = 'Hot utility'
                stream_dest = stream_id

        else:
            if stream_id not in hot_df[STFM.ID.name].values:
                raise KeyError("Stream {0} not found.".format(stream_id))
            else:
                stream_info = hot_df.loc[hot_df[STFM.ID.name] == stream_id, :]
                coef = hot_df.loc[
                    hot_df[STFCFM.ID.name] == stream_id,
                    STFCFM.COEF.name
                ].item()

                stream_source = stream_id
                stream_dest = 'Cold utility'

        cp = stream_info[STFM.CP.name].item()
        mf = stream_info[STFM.FLOW.name].item()

        if utility_type == 'hot':
            # if the stream_id (cold) already receives heat, get maximum
            # cold outlet temperature
            if stream_id in design[HEDFM.DEST.name].values:
                # maximum outlet temperature
                tin = design.loc[
                    design[HEDFM.DEST.name] == stream_id,
                    HEDFM.COLD_OUT.name
                ].max()
            else:
                tin = stream_info[STFM.TIN.name].item()

            tout = stream_info[STFM.TOUT.name].item()

        else:
            # if the stream_id (hot) already receives heat, get the minimum
            # hot outlet temperature
            if stream_id in design[HEDFM.SOURCE.name].values:
                # minimum inlet temperature
                tin = design.loc[
                    design[HEDFM.SOURCE.name] == stream_id,
                    HEDFM.HOT_OUT.name
                ].min()
            else:
                tin = stream_info[STFM.TIN.name].item()

            tout = stream_info[STFM.TOUT.name].item()

        # 4 digits rounding
        if duty > np.around(np.abs(mf * cp * (tin - tout)), 4):
            raise ValueError("The specified heat duty is not feasible for the "
                             "stream.")
        else:
            # actual outlet temperature
            if utility_type == 'hot':
                tout = tin + duty / (mf * cp)

                h_tin = ut_in
                h_tout = ut_out
                c_tin = tin
                c_tout = tout
                hot_coef = ut_coef
                cold_coef = coef
            else:
                tout = tin - duty / (mf * cp)

                h_tin = tin
                h_tout = tout
                c_tin = ut_in
                c_tout = ut_out
                hot_coef = coef
                cold_coef = ut_coef

        # log mean correction factor
        f = factor

        # log mean temp
        dtln = calculate_log_mean_diff('counter', h_tin, h_tout, c_tin, c_tout)

        # area and overall heat coefficient
        a, u = calculate_exchanger_area(duty, dtln, hot_coef, cold_coef, f)

        # exchanger costs
        cbm = calculate_bare_module_cost(ex_type, arrangement, shell_mat,
                                         tube_mat, a, pressure)

        # store the exchanger data
        new_row = {
            HEDFM.ID.name: ex_id,
            HEDFM.INT.name: interval,
            HEDFM.DUTY.name: duty,
            HEDFM.COST.name: cbm,
            HEDFM.TYPE.name: ex_type.value,
            HEDFM.ARRANGEMENT.name: arrangement.value,
            HEDFM.SHELL.name: shell_mat.value,
            HEDFM.TUBE.name: tube_mat.value,
            HEDFM.SOURCE.name: stream_source,
            HEDFM.DEST.name: stream_dest,
            HEDFM.HOT_IN.name: h_tin,
            HEDFM.HOT_OUT.name: h_tout,
            HEDFM.COLD_IN.name: c_tin,
            HEDFM.COLD_OUT.name: c_tout,
            HEDFM.DT.name: dtln,
            HEDFM.U.name: u,
            HEDFM.F.name: f,
            HEDFM.A.name: a,
            HEDFM.NSHELL.name: 0
        }

        design = design.append(new_row, ignore_index=True)
        if des_type == 'abv':
            self.design_above = design
        else:
            self.design_below = design

    def delete_exchanger(self, ex_id: str, des_type: str) -> None:
        # input sanitation
        if des_type == 'abv':
            design = self.design_above
        elif des_type == 'blw':
            design = self.design_below
        else:
            raise ValueError("Invalid design choice.")

        design = design.set_index(HEDFM.ID.name)
        design = design.drop(labels=ex_id, axis='index')
        design = design.reset_index(drop=False)

        if des_type == 'abv':
            self.design_above = design
        else:
            self.design_below = design

    def load(self, filename: str) -> None:
        check_file_exists(filename)

        with open(filename, 'r') as fp:
            hsd = json.load(fp)

        # ------------------------------ Streams ------------------------------
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

        # ------------------------------- Films -------------------------------

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

        # ------------------------------ Designs ------------------------------
        design = hsd['design']
        design_above = pd.DataFrame(design['above']['exchangers'])
        design_above = design_above.astype(
            {key: float if key not in HEDFM_STR_COLS else object
             for key in HEDFM.columns()}
        )
        design_above.index = design_above.index.astype(int)

        hot_above = pd.DataFrame(design['above']['hot'])
        hot_above = hot_above.astype(
            {key: float if key != STFM.ID.name else object
             for key in STFM.columns()}
        )
        hot_above.index = hot_above.index.astype(int)

        cold_above = pd.DataFrame(design['above']['cold'])
        cold_above = cold_above.astype(
            {key: float if key != STFM.ID.name else object
             for key in STFM.columns()}
        )
        cold_above.index = cold_above.index.astype(int)

        design_below = pd.DataFrame(design['below']['exchangers'])
        design_below = design_below.astype(
            {key: float if key not in HEDFM_STR_COLS else object
             for key in HEDFM.columns()}
        )
        design_below.index = design_below.index.astype(int)

        hot_below = pd.DataFrame(design['below']['hot'])
        hot_below = hot_below.astype(
            {key: float if key != STFM.ID.name else object
             for key in STFM.columns()}
        )
        hot_below.index = hot_below.index.astype(int)

        cold_below = pd.DataFrame(design['below']['cold'])
        cold_below = cold_below.astype(
            {key: float if key != STFM.ID.name else object
             for key in STFM.columns()}
        )
        cold_below.index = cold_below.index.astype(int)

        # ---------------------------------------------------------------------

        self.blockSignals(True)

        self.hot = hot
        self.cold = cold

        self.blockSignals(False)

        self.hot_film_coef = hot_film
        self.cold_film_coef = cold_film

        self.dt = hsd['dt']

        self._hot_above = hot_above
        self._cold_above = cold_above
        self._hot_below = hot_below
        self._cold_below = cold_below
        self.design_above = design_above
        self.design_below = design_below

    def save(self, filename: str) -> None:
        dump = {
            'dt': self.dt,
            'hot': self.hot.to_dict(),
            'cold': self.cold.to_dict(),
            'hot_film': self.hot_film_coef.to_dict(),
            'cold_film': self.cold_film_coef.to_dict(),
            'design': {
                'above': {
                    'exchangers': self.design_above.to_dict(),
                    'hot': self.hot_above.to_dict(),
                    'cold': self.cold_above.to_dict()
                },
                'below': {
                    'exchangers': self.design_below.to_dict(),
                    'hot': self.hot_below.to_dict(),
                    'cold': self.cold_below.to_dict()
                }

            }
        }

        with open(filename, 'w') as fp:
            json.dump(dump, fp, indent=4)


def check_file_exists(filename: str) -> None:
    filepath = pathlib.Path(filename).resolve()

    if not filepath.exists() or not filepath.is_file():
        raise FileNotFoundError("Invalid .hsd file specified.")
