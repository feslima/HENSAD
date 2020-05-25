import pandas as pd
import numpy as np
from typing import Union, List, TypedDict, Tuple, Type
from enum import Enum, unique
from abc import ABC, abstractmethod


@unique
class FrameColumnMapperEnum(Enum):
    @classmethod
    def columns(cls) -> list:
        return list(map(lambda c: c.name, cls))

    @classmethod
    def headers(cls) -> list:
        return list(map(lambda c: c.value, cls))


@unique
class StreamFrameMapper(FrameColumnMapperEnum):
    FLOW = 'Mass flow rate'
    CP = 'Specific Heat Capacity'
    TIN = 'Inlet Temperature'
    TOUT = 'Outlet Temperature'


@unique
class SummaryFrameMapper(FrameColumnMapperEnum):
    INTERVAL = 'Interval Name'
    TIN = 'Initial Temperature'
    TOUT = 'Final Temperature'
    EXHEAT = 'Excess Heat'
    CUMHEAT = 'Cumulative Heat'


@unique
class HeatFlowFrameMapper(FrameColumnMapperEnum):
    UTIL = 'Hot Utility Flow'
    OUT = 'Heat Out'
    EXHEAT = 'Excess Heat'


class BaseUnits(ABC):
    @property
    def mass(self) -> str:
        """Mass unit."""
        return self._mass

    @property
    def power(self) -> str:
        """Power unit."""
        return self._power

    @property
    def temperature(self) -> str:
        """Temperature unit."""
        return self._temperature

    @property
    def area(self) -> str:
        """Area unit."""
        return self._area

    @property
    def energy(self) -> str:
        """Energy unit."""
        return self._energy

    @property
    def time(self) -> str:
        """Time unit."""
        return self._time

    @property
    def mass_flow(self) -> str:
        """Mass flowrate unit."""
        return self.mass + self._sep + self.time

    @property
    def energy_flow(self) -> str:
        """Energy flowrate unit."""
        return self.energy + self._sep + self.time

    @property
    def heat_capacity(self) -> str:
        """"""
        return self.energy + self._sep + self.mass + \
            self._sep + self.temperature

    @property
    def heat_coeff(self) -> str:
        """Heat Transfer Coefficient unit."""
        return self.energy + self._sep + self.area + \
            self._sep + self.temperature

    @abstractmethod
    def __init__(self):
        self._sep = '/'
        self._mass = ''
        self._power = ''
        self._temperature = ''
        self._area = ''
        self._energy = ''
        self._time = 's'


class SIUnits(BaseUnits):
    def __init__(self):
        super().__init__()
        self._mass = 'kg'
        self._power = 'kW'
        self._temperature = '°C'
        self._area = 'm^2'
        self._energy = 'kJ'


class USUnits(BaseUnits):
    def __init__(self):
        super().__init__()
        self._mass = 'lb'
        self._power = 'BTU/h'
        self._temperature = '°F'
        self._area = 'ft^2'
        self._energy = 'BTU'
        self._time = 'h'


def calculate_summary_table(hot: pd.DataFrame, cold: pd.DataFrame,
                            dt: float) -> pd.DataFrame:
    if not isinstance(hot, pd.DataFrame) or not isinstance(cold, pd.DataFrame):
        raise TypeError("Hot and cold streams frames must be a DataFrame.")

    if hot.empty or cold.empty:
        raise ValueError("Hot and cold stream can't be empty")

    if not isinstance(dt, float):
        raise TypeError("Minimum temperature approach must be a float.")
    else:
        if dt <= 0 or np.isnan(dt):
            raise ValueError("Minimum temperature approach value has to be "
                             "positive.")

    SFM = SummaryFrameMapper
    STFM = StreamFrameMapper
    intervals = pd.DataFrame(columns=SFM.columns())
    intervals = intervals.astype(
        {
            SFM.INTERVAL.name: object,
            SFM.TIN.name: float,
            SFM.TOUT.name: float,
            SFM.EXHEAT.name: float,
            SFM.CUMHEAT.name: float
        }
    )

    hot = hot.astype(
        {
            STFM.TIN.name: float,
            STFM.TOUT.name: float,
            STFM.FLOW.name: float,
            STFM.CP.name:  float
        }
    )

    cold = cold.astype(
        {
            STFM.TIN.name: float,
            STFM.TOUT.name: float,
            STFM.FLOW.name: float,
            STFM.CP.name:  float
        }
    )

    hint, _ = calculate_intervals(hot, cold, dt)

    for i in range(hint.size - 1):
        itin = hint[i]
        itout = hint[i + 1]

        intervals.at[i, SummaryFrameMapper.INTERVAL.name] = f'I-{i+1}'
        intervals.at[i, SFM.TIN.name] = itin
        intervals.at[i, SFM.TOUT.name] = itout

        # classify streams indexes by intervals
        hot_streams = []
        for s in range(hot.shape[0]):
            hot_in = hot.at[s, STFM.TIN.name]
            hot_out = hot.at[s, STFM.TOUT.name]
            if hot_in == itin or hot_out == itout or \
                    (hot_in >= itin and hot_out <= itout):
                hot_streams.append(s)
        hot_streams = sorted(hot_streams)

        cold_streams = []
        for s in range(cold.shape[0]):
            cold_in = cold.at[s, STFM.TIN.name]
            cold_out = cold.at[s, STFM.TOUT.name]
            if (cold_in + dt) == itout or (cold_out + dt) == itin or \
                    ((cold_in + dt) <= itout and (cold_out + dt) >= itin):
                cold_streams.append(s)
        cold_streams = sorted(cold_streams)

        # calculate the excess and cumulative heat
        exheat = 0.0
        for s in hot_streams:
            exheat += hot.at[s, STFM.FLOW.name] * \
                hot.at[s, STFM.CP.name] * (itin - itout)
        for s in cold_streams:
            exheat += cold.at[s, STFM.FLOW.name] * \
                cold.at[s, STFM.CP.name] * (itout - itin)

        intervals.at[i, SFM.EXHEAT.name] = exheat

        if i == 0:
            intervals.at[i, SFM.CUMHEAT.name] = exheat
        else:
            intervals.at[i, SFM.CUMHEAT.name] = exheat + \
                intervals.at[i - 1, SFM.CUMHEAT.name]

    return intervals


def calculate_intervals(hot: pd.DataFrame, cold: pd.DataFrame,
                        dt: float) -> Tuple[np.ndarray, np.ndarray]:
    STFM = StreamFrameMapper
    hot_in = hot[STFM.TIN.name]
    hot_out = hot[STFM.TOUT.name]
    cold_in = cold[STFM.TIN.name]
    cold_out = cold[STFM.TOUT.name]

    # find all the unique temperature values
    h_t = np.append(hot_in, hot_out)
    c_t = np.append(cold_in, cold_out)
    u_h_t = np.unique(h_t)
    u_c_t = np.unique(c_t)

    # add the Difference Temperature to the cold side
    # values and get hot/cold side ticks and number of
    # temperature intervals
    hot_int = np.unique(np.append(u_h_t, u_c_t + dt))
    cold_int = hot_int - dt
    hot_int = np.flip(hot_int)  # sort the temperature from largest to smallest

    return hot_int, cold_int


def calculate_pinch_utilities(
    summary: pd.DataFrame
) -> Tuple[float, float, float]:
    SFM = SummaryFrameMapper
    exheat = summary[SFM.EXHEAT.name].to_numpy()

    # find the index of the first excess
    idx = 0
    if exheat[idx] < 0:
        heat_pre_pinch = exheat[idx]
    else:
        heat_pre_pinch = 0

    while idx < exheat.size:
        if exheat[idx] > 0:
            break
        else:
            idx += 1

    # keep the sum until the pinch is found or the list ends
    pinch_idx = None
    huq = heat_pre_pinch
    for i in range(idx, exheat.size):
        huq += exheat[i]

        if huq < 0:
            pinch_idx = i
            break

    huq = np.abs(huq)
    if pinch_idx is None:
        cuq = 0.0  # There is no pinch
        hot_t_pinch = np.NaN
    else:
        cuq = exheat[(pinch_idx+1):].sum()
        hot_t_pinch = summary.at[pinch_idx, SFM.TOUT.name]

    return hot_t_pinch, huq, cuq


def pinch_streams_tables(
    hot: pd.DataFrame, cold: pd.DataFrame,
    dt: float, pinch: float
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # INDEXES ARE NOT RESETTED!
    SFM = SummaryFrameMapper
    STFM = StreamFrameMapper
    if np.isnan(pinch):
        # no pinch
        empty_frame = pd.DataFrame(columns=STFM.columns())

        hot_above = hot.copy(deep=True)
        cold_above = cold.copy(deep=True)

        hot_below = empty_frame.copy(deep=True)
        cold_below = empty_frame.copy(deep=True)

    else:
        # split the streams
        # above section
        index_hot_abv = hot[STFM.TIN.name] >= pinch
        hot_above = hot.loc[index_hot_abv, :]

        index_cold_abv = cold[STFM.TOUT.name] >= (pinch - dt)
        cold_above = cold.loc[index_cold_abv, :]

        # replace temperatures below pinch with pinch value
        hot_above.loc[
            hot_above[STFM.TOUT.name] < pinch,
            STFM.TOUT.name
        ] = pinch  # cap hot outlet at pinch

        cold_above.loc[
            cold_above[STFM.TIN.name] < (pinch - dt),
            STFM.TIN.name
        ] = (pinch - dt)  # cap cold inlet at pinch

        # below section
        index_hot_blw = hot[STFM.TOUT.name] < pinch
        hot_below = hot.loc[index_hot_blw, :]

        index_cold_blw = cold[STFM.TIN.name] < (pinch - dt)
        cold_below = cold.loc[index_cold_blw, :]

        hot_below.loc[
            hot_below[STFM.TIN.name] >= pinch,
            STFM.TIN.name
        ] = pinch  # cap hot inlet at pinch

        cold_below.loc[
            cold_below[STFM.TOUT.name] >= (pinch - dt),
            STFM.TOUT.name
        ] = (pinch - dt)  # cap cold outlet at pinch

    return hot_above, cold_above, hot_below, cold_below


def calculate_minimum_exchangers(
    hot: pd.DataFrame, cold: pd.DataFrame, section: str
) -> int:
    num_hot_util = 1 if section == 'above' else 0
    num_cold_util = 1 if section == 'below' else 0

    # equation 15.1
    return len(hot) + len(cold) + num_hot_util + num_cold_util - 1


def calculate_heat_flows(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        raise ValueError("Can't determine heat flows on an empty summary.")

    heat_flow = pd.DataFrame(columns=HeatFlowFrameMapper.columns())
    heat_flow = heat_flow.astype({c: float for c in heat_flow.columns})

    n_intervals = len(summary)

    out_prev = 0.0
    i = 0
    while i < n_intervals:
        exheat = summary.at[i, SummaryFrameMapper.EXHEAT.name]
        out = out_prev + exheat

        if out <= 0.0:
            # no excess heat enough to be dumped
            util = np.abs(out)
            out = 0.0

        else:
            util = 0.0

        heat_flow.loc[i, heat_flow.columns] = [util, out, exheat]

        i += 1
        out_prev = out

    return heat_flow
