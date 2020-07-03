from abc import ABC, abstractmethod
from enum import Enum, unique
from typing import List, Tuple, Type, TypedDict, Union

import numpy as np
import pandas as pd

from .cost import (ArrangementType, ExchangerType, MaterialType,
                   calculate_bare_module_cost)

_ROUND_OFF = 4  # digits to round off in interval comparisons


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
    ID = 'Stream ID'
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
    HOTSTRIDX = 'Hot Stream Index'
    COLDSTRIDX = 'Cold Stream Index'


@unique
class HeatFlowFrameMapper(FrameColumnMapperEnum):
    UTIL = 'Hot Utility Flow'
    OUT = 'Heat Out'
    EXHEAT = 'Excess Heat'


@unique
class HeatExchangerDesignFrameMapper(FrameColumnMapperEnum):
    ID = 'Exchanger ID'
    INT = 'Interval'
    DUTY = 'Heat Duty'
    SOURCE = 'Stream Source'
    DEST = 'Stream Destination'
    TYPE = 'Exchanger Type'
    HOT_IN = 'Hot Stream Inlet'
    HOT_OUT = 'Hot Stream Outlet'
    COLD_IN = 'Cold Stream Inlet'
    COLD_OUT = 'Cold Stream Outlet'
    DT = 'Delta T (lm)'
    U = 'Heat Transfer Coefficient'
    A = 'Exchange Area'
    NSHELL = 'Shell Passes'
    F = 'Correction Factor'


@unique
class FilmCoefficientsFrameMapper(FrameColumnMapperEnum):
    ID = 'Stream ID'
    COEF = 'Film Heat Transfer Coefficient'


@unique
class StreamFilmCoefficientFrameMapper(FrameColumnMapperEnum):
    ID = 'Stream ID'
    FLOW = 'Mass flow rate'
    CP = 'Specific Heat Capacity'
    TIN = 'Inlet Temperature'
    TOUT = 'Outlet Temperature'
    COEF = 'Film Heat Transfer Coefficient'


@unique
class SegmentsFrameMapper(FrameColumnMapperEnum):
    HOT_IN = 'Hot Inlet'
    HOT_OUT = 'Hot Outlet'
    COLD_IN = 'Cold Inlet'
    COLD_OUT = 'Cold Outlet'
    DTLN = 'Log Mean Temperature Difference'
    Q = 'Interval Enthalpy'
    SUM_QH = 'Sum of Enthalpy - Coefficient ratio'


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

        intervals.at[i, SFM.HOTSTRIDX.name] = hot_streams
        intervals.at[i, SFM.COLDSTRIDX.name] = cold_streams

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

    n = len(summary)

    for i in range(n - 1, 0, -1):
        # start from last block upwards
        ex_heat = summary.at[i, SFM.EXHEAT.name]

        if ex_heat <= 0 and i != (n - 1):
            pinch_idx = i  # previous block
            if summary.at[i + 1, SFM.EXHEAT.name] <= 0:
                pinch_idx = None  # fall back in case last block has no exheat

            break

    if pinch_idx is None:
        # There is no pinch
        huq = np.abs(summary[SFM.EXHEAT.name].sum().item())
        cuq = 0.0
        hot_t_pinch = np.NaN
    else:
        huq = abs(summary.loc[0:pinch_idx, SFM.EXHEAT.name].sum().item())
        cuq = abs(summary.loc[
            (pinch_idx + 1):(n - 1),
            SFM.EXHEAT.name
        ].sum().item())
        hot_t_pinch = summary.at[pinch_idx, SFM.TOUT.name]

    return hot_t_pinch, huq, cuq


def pinch_streams_tables(
    hot: pd.DataFrame, cold: pd.DataFrame,
    dt: float, pinch: float, hot_film: pd.DataFrame, cold_film: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # INDEXES ARE NOT RESETTED!
    SFM = SummaryFrameMapper
    STFM = StreamFrameMapper
    FCFM = FilmCoefficientsFrameMapper
    STFCFM = StreamFilmCoefficientFrameMapper
    if np.isnan(pinch):
        # no pinch
        empty_frame = pd.DataFrame(columns=STFCFM.columns())

        hot_above = hot.copy(deep=True)
        cold_above = cold.copy(deep=True)

        hot_below = empty_frame.copy(deep=True)
        cold_below = empty_frame.copy(deep=True)

    else:
        # split the streams
        hot_pinch = np.around(pinch, _ROUND_OFF)
        cold_pinch = np.around(pinch - dt, _ROUND_OFF)
        # above section
        index_hot_abv = hot[STFM.TIN.name] >= hot_pinch
        hot_above = hot.loc[index_hot_abv, :]

        index_cold_abv = cold[STFM.TOUT.name] >= cold_pinch
        cold_above = cold.loc[index_cold_abv, :]

        # replace temperatures below pinch with pinch value
        hot_above.loc[
            hot_above[STFM.TOUT.name] < hot_pinch,
            STFM.TOUT.name
        ] = hot_pinch  # cap hot outlet at pinch

        hot_above = hot_above.set_index(STFM.ID.name).join(
            hot_film.set_index(FCFM.ID.name)
        ).reset_index()  # append the film coefficients

        cold_above.loc[
            cold_above[STFM.TIN.name] < cold_pinch,
            STFM.TIN.name
        ] = cold_pinch  # cap cold inlet at pinch

        cold_above = cold_above.set_index(STFM.ID.name).join(
            cold_film.set_index(FCFM.ID.name)
        ).reset_index()  # append the film coefficients

        # below section
        index_hot_blw = hot[STFM.TOUT.name] < hot_pinch
        hot_below = hot.loc[index_hot_blw, :]

        index_cold_blw = cold[STFM.TIN.name] < cold_pinch
        cold_below = cold.loc[index_cold_blw, :]

        hot_below.loc[
            hot_below[STFM.TIN.name] >= hot_pinch,
            STFM.TIN.name
        ] = hot_pinch  # cap hot inlet at pinch

        hot_below = hot_below.set_index(STFM.ID.name).join(
            hot_film.set_index(FCFM.ID.name)
        ).reset_index()  # append the film coefficients

        cold_below.loc[
            cold_below[STFM.TOUT.name] >= cold_pinch,
            STFM.TOUT.name
        ] = cold_pinch  # cap cold outlet at pinch

        cold_below = cold_below.set_index(STFM.ID.name).join(
            cold_film.set_index(FCFM.ID.name)
        ).reset_index()  # append the film coefficients

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


def calculate_log_mean_diff(ex_type: str, hot_in: float, hot_out: float,
                            cold_in: float, cold_out: float) -> float:
    """Calculates the log mean temperature difference for either co-current or
    counter-current exchangers.

    Parameters
    ----------
    ex_type : str
        Exchanter type: 'co' for co-current, 'counter' for counter-current.
    hot_in : float
        Hot inlet temperature.
    hot_out : float
        Hot outlet temperature.
    cold_in : float
        Cold inlet temperature.
    cold_out : float
        Cold outlet temperature.


    Returns
    -------
    float
        Log mean temperature difference value.
    """
    if ex_type == 'co':
        DTA = hot_in - cold_in
        DTB = hot_out - cold_out
    elif ex_type == 'counter':
        DTA = hot_in - cold_out
        DTB = hot_out - cold_in
    else:
        raise ValueError("Invalid approach type.")

    if np.isclose(DTA, DTB):
        LMTD = DTA
    else:
        LMTD = (DTA - DTB) / np.log(DTA / DTB)

    return LMTD


class Stream(TypedDict):
    ID: str
    FLOW: float
    CP: float
    TIN: float
    TOUT: float


def calculate_number_of_shells(
    hot: Stream, cold: Stream
) -> int:
    """Get the number of sheels for a 1-2 S&T heat exchanger.

    Parameters
    ----------
    hot : Stream
        Hot side stream.
    cold : Stream
        Cold side stream.

    Returns
    -------
    int
        Number of shells.
    """
    R = (cold['FLOW'] * cold['CP']) / (hot['FLOW'] * hot['CP'])

    tc_in = cold['TIN']
    tc_out = cold['TOUT']
    th_in = hot['TIN']
    th_out = hot['TOUT']
    P = (tc_out - tc_in) / (th_in - tc_in)

    if R != 1.0:
        n_shells = np.log((1 - P * R) / (1 - P)) / np.log(1 / R)
    else:
        n_shells = P / (1 - P)

    return np.ceil(n_shells).item()


def calculate_exchanger_area(
    duty: float, dtln: float, hot_coefs: List[float],
    cold_coefs: List[float], factor: float
) -> Tuple[float, float]:
    """Calculates the exchanger area and overall heat transfer coefficient.

    Parameters
    ----------
    duty : float
        Heat exchanger duty.
    dtln : float
        Log mean temperature difference.
    hot_coefs : List[float]
        Hot side heat transfer film coefficients.
    cold_coefs : List[float]
        Cold side heat transfer film coefficients.
    factor : float
        Correction factor.

    Returns
    -------
    Tuple[float, float]
        Tuple of two elements. First one is the exchanger area. The second is
        the overall heat transfer coefficient.
    """
    u = 1 / (1 / np.array(hot_coefs) + 1 / np.array(cold_coefs)).sum()
    a = duty * 1e3 / (u * dtln * factor)

    return a, u


def calculate_composite_enthalpy(
        hot: pd.DataFrame, cold: pd.DataFrame,
        dt: float, huq: float, cuq: float,
        hot_coefs: pd.DataFrame, cold_coefs: pd.DataFrame,
        summary: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Calculates the composite enthalpy data for curve plots.

    Parameters
    ----------
    hot : pd.DataFrame
        Hot stream info.
    cold : pd.DataFrame
        Cold stream info.
    dt : float
        Minimum approach temperature difference.
    huq : float
        Hot utility requirement.
    cuq : float
        Cold utility requirement.
    hot_coefs : pd.DataFrame
        Hot streams film coefficients.
    cold_coefs : pd.DataFrame
        Cold streams film coefficients.

    Returns
    -------
    Tuple[pd.DataFrame, pd.DataFrame]
        Tuple of two elements. The first is hot streams composite curve. The
        second is the cold streams curve.
    """
    SFM = SummaryFrameMapper
    STFM = StreamFrameMapper

    hTQ = pd.DataFrame(columns=['Q', 'T'], dtype=float)
    cTQ = pd.DataFrame(columns=['Q', 'T'], dtype=float)

    hs = summary.sort_values(
        by=SFM.TIN.name, ascending=True, ignore_index=True
    )

    # cumulative heats
    hcumq = 0.0
    ccumq = cuq

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

    return hTQ, cTQ


def _search_enthalpy_interval(
    Q: float, composite: pd.DataFrame
) -> Tuple[float, float, float, float]:
    """For a given enthalpy 'Q', search the interval
    values of 'composite' that contains the 'Q' value.

    Parameters
    ----------
    Q : float
        Enthalpy value.
    composite: pd.DataFrame
        Composite enthalpy curves to be searched.

    Returns
    -------
    Tuple[float, float, float, float]
        The linear interval that contains the initial and final values of 
        enthalpy and temperature. Tuple of four elements with the order as:
        lower enthalpy, lower temperature, upper enthalpy, upper temperature.

    Notes
    -----
    If the enthalpy value 'Q' is not present in the 'composite' curve, the 
    function will return a tuple of all NaNs.
    """
    qlb, tlb, qub, tub = np.nan, np.nan, np.nan, np.nan

    for i in range(len(composite) - 1):
        lb = composite.at[i, 'Q']
        ub = composite.at[i + 1, 'Q']

        if lb <= Q <= ub and not np.isclose(lb, ub):
            qlb = lb
            qub = ub
            tlb = composite.at[i, 'T']
            tub = composite.at[i + 1, 'T']
            break

    return qlb, tlb, qub, tub


def _interpolate_temperature_in_interval(
    Q: float, Qi: float, Ti: float, Qf: float, Tf: float
) -> float:
    """Interpolate the enthalpy 'Q' value to find its corresponding temperature
    in the interval delimited by ['Qi', 'Ti'] and ['Qf', 'Tf']self.

    Parameters
    ----------
    Q : float
        Enthalpy value to be linearly interpolatedself.
    Qi : float
        Initial value of enthalpy interval.
    Ti : float
        Initial value of temperature interval.
    Qf : float
        Final value of enthalpy interval.
    Tf : float
        Final value of temperature interval.

    Returns
    -------
    float
        The resulting interpolated temperature from 'Q'.
    """
    # Temperature = A * Enthalpy + b
    enthalpy = np.array([[Qf, 1.0], [Qi, 1.0]])
    temperature = np.array([Tf, Ti])

    A, b = np.linalg.solve(enthalpy, temperature)

    return A * Q + b


def _build_composite_borders(hot_composite: pd.DataFrame,
                             cold_composite: pd.DataFrame) -> pd.DataFrame:
    """Builds the vertical borders of the composite enthalpy diagram. The
    borders can be clearly visualized in Fig E15.5 of Analysis, Synthesis and
    Design of Chemical Processes (Third Edition).

    Parameters
    ----------
    hot_composite : pd.DataFrame
        Hot streams composite enthalpy curve.
    cold_composite : pd.DataFrame
        Cold streams composite enthalpy curve.

    Returns
    -------
    pd.DataFrame
        Values of temperature and enthalpy of each segment border.
    """
    hTQ = hot_composite
    cTQ = cold_composite

    # a border is defined as a single vertical line at a Q value
    new_borders = []
    for i in range(len(cTQ)):
        # each iteration we determine two borders
        cQ, cT = cTQ.loc[i, ['Q', 'T']]
        hQ, hT = hTQ.loc[i, ['Q', 'T']]

        if i == 0:
            # first border
            # temperatures of first border of iteration
            tH1 = hT
            tC1 = np.NaN

            # temperatures of second border of iteration
            Qi, Ti, Qf, Tf = _search_enthalpy_interval(cQ, hTQ)
            tH2 = _interpolate_temperature_in_interval(cQ, Qi, Ti, Qf, Tf)
            tC2 = cT

        elif i == (len(cTQ) - 1):
            # last border
            tH1 = hT
            Qi, Ti, Qf, Tf = _search_enthalpy_interval(hQ, cTQ)
            tC1 = _interpolate_temperature_in_interval(hQ, Qi, Ti, Qf, Tf)

            tH2 = np.NaN
            tC2 = cT

        else:
            # middle borders
            tH1 = _interpolate_temperature_in_interval(
                hQ, *_search_enthalpy_interval(hQ, hTQ)
            )
            tC1 = _interpolate_temperature_in_interval(
                hQ, *_search_enthalpy_interval(hQ, cTQ)
            )
            tH2 = _interpolate_temperature_in_interval(
                cQ, *_search_enthalpy_interval(cQ, hTQ)
            )
            tC2 = _interpolate_temperature_in_interval(
                cQ, *_search_enthalpy_interval(cQ, cTQ)
            )

        new_borders.append([
            {'hot': tH1, 'cold': tC1, 'Q': hQ},
            {'hot': tH2, 'cold': tC2, 'Q': cQ}
        ])

    borders = pd.concat(
        [pd.DataFrame(border) for border in new_borders],
        ignore_index=True
    )

    # sort by enthalpy value to ensure correct order of borders
    borders.sort_values(by='Q', inplace=True, ignore_index=True)

    # if there is a pinch, a duplicated border (row) will appear. Drop them
    borders.drop_duplicates(ignore_index=True, inplace=True)

    # drop duplicated vertical segments to avoid overestimation of areas
    borders.drop_duplicates('hot', keep='last',
                            ignore_index=True, inplace=True)
    borders.drop_duplicates('cold', keep='first',
                            ignore_index=True, inplace=True)
    return borders


def _find_streams_in_interval(
    t1: float, t2: float, summary: pd.DataFrame, dt: float = None
) -> int:
    SFM = SummaryFrameMapper
    STFM = StreamFrameMapper

    if dt is None:
        # this means that we want the hot streams
        dt = 0.0  # do not change from hot to cold
        STRIDX = SFM.HOTSTRIDX.name

    else:
        STRIDX = SFM.COLDSTRIDX.name

    int_out = (summary[SFM.TOUT.name] - dt).round(_ROUND_OFF)
    int_in = (summary[SFM.TIN.name] - dt).round(_ROUND_OFF)

    start_index = summary.index[
        np.logical_and(int_in > t1, t1 >= int_out)
    ].values.item()
    end_index = summary.index[
        np.logical_and(int_in >= t2, t2 > int_out)
    ].values.item()

    if start_index > end_index:
        # swap start and end indexes
        tmp_idx = start_index
        start_index = end_index
        end_index = tmp_idx

    # get unique indexes of streams
    indexes = np.unique(
        np.concatenate(
            summary.loc[start_index:end_index, STRIDX].values
        ).ravel().astype(int)
    ).tolist()

    return indexes


def calculate_segments_data(
    hot: pd.DataFrame, cold: pd.DataFrame,
    dt: float, hot_composite: pd.DataFrame, cold_composite: pd.DataFrame,
    hot_coefs: pd.DataFrame, cold_coefs: pd.DataFrame, summary: pd.DataFrame
) -> pd.DataFrame:
    """Calculates the data needed to estimate the total area of a heat
    exchanger network.

    Parameters
    ----------
    hot : pd.DataFrame
        Hot streams.
    cold : pd.DataFrame
        Cold streams.
    dt : float
        Minimum approach temperature difference.
    hot_composite : pd.DataFrame
        Hot streams composite enthalpy curve.
    cold_composite : pd.DataFrame
        Cold streams composite enthalpy curve.
    hot_coefs : pd.DataFrame
        Hot streams film coefficients.
    cold_coefs : pd.DataFrame
        Cold streams film coefficients.
    summary : pd.DataFrame
        Summary table of the temperature intervals.

    Returns
    -------
    pd.DataFrame
        Segment data to estimate heat exchanger network area.
    """

    SFM = SummaryFrameMapper
    STFM = StreamFrameMapper
    FCFM = FilmCoefficientsFrameMapper
    SEGFM = SegmentsFrameMapper

    stream_ids = hot.loc[:, STFM.ID.name].values.tolist() + \
        cold.loc[:, STFM.ID.name].values.tolist()

    segments = pd.DataFrame(columns=stream_ids + SEGFM.columns())

    hTQ = hot_composite
    cTQ = cold_composite

    borders = _build_composite_borders(hTQ, cTQ)

    for i in range(len(borders) - 1):
        if borders.loc[i, ['hot', 'cold']].notna().all(axis=None) and \
                borders.loc[i + 1, ['hot', 'cold']].notna().all(axis=None):
            # fill the temperature intervals
            # rounding to 6 decimals due floating point bugs in Q calculations
            hot_1 = np.around(borders.at[i, 'hot'], decimals=_ROUND_OFF)
            hot_2 = np.around(borders.at[i + 1, 'hot'], decimals=_ROUND_OFF)
            segments.at[i, SEGFM.HOT_IN.name] = hot_1
            segments.at[i, SEGFM.HOT_OUT.name] = hot_2

            cold_1 = np.around(borders.at[i, 'cold'], decimals=_ROUND_OFF)
            cold_2 = np.around(borders.at[i + 1, 'cold'], decimals=_ROUND_OFF)
            segments.at[i, SEGFM.COLD_IN.name] = cold_1
            segments.at[i, SEGFM.COLD_OUT.name] = cold_2

            segments.at[i, SEGFM.Q.name] = borders.at[i + 1, 'Q'] \
                - borders.at[i, 'Q']

            # log mean temperature
            segments.at[i, SEGFM.DTLN.name] = calculate_log_mean_diff(
                'co', hot_1, hot_2, cold_1, cold_2)

            # get stream indexes
            hot_idx = _find_streams_in_interval(hot_1, hot_2, summary)
            cold_idx = _find_streams_in_interval(cold_1, cold_2, summary, dt)

            # calculate stream enthalpies by interval
            sum_Qh = 0.0
            for idx in hot_idx:
                stream = hot.at[idx, STFM.ID.name]
                cp = hot.at[idx, STFM.CP.name]
                mf = hot.at[idx, STFM.FLOW.name]
                coef = hot_coefs.at[idx, FCFM.COEF.name] / 1000

                Q = mf * cp * (hot_2 - hot_1)

                sum_Qh += Q / coef

                segments.at[i, stream] = Q

            for idx in cold_idx:
                stream = cold.at[idx, STFM.ID.name]
                cp = cold.at[idx, STFM.CP.name]
                mf = cold.at[idx, STFM.FLOW.name]
                coef = cold_coefs.at[idx, FCFM.COEF.name] / 1000

                Q = mf * cp * (cold_2 - cold_1)

                sum_Qh += Q / coef

                segments.at[i, stream] = Q

            # insert ratio values
            segments.at[i, SEGFM.SUM_QH.name] = sum_Qh

    segments = segments.fillna(0.0)

    return segments


def calculate_eaoc(hot: pd.DataFrame, cold: pd.DataFrame, dt: float,
                   hot_coefs: pd.DataFrame, cold_coefs: pd.DataFrame,
                   extype: ExchangerType, arrangement: ArrangementType,
                   shell_mat: MaterialType, tube_mat: MaterialType,
                   pressure: float) -> Tuple[float, float, float, float, int]:
    SEGFM = SegmentsFrameMapper

    # get the heat exchanger network area estimate
    summary = calculate_summary_table(hot, cold, dt)
    pinch, huq, cuq = calculate_pinch_utilities(summary)
    hTQ, cTQ = calculate_composite_enthalpy(hot, cold, dt, huq, cuq,
                                            hot_coefs, cold_coefs, summary)
    segments = calculate_segments_data(hot, cold, dt, hTQ, cTQ, hot_coefs,
                                       cold_coefs, summary)

    netarea = (segments[SEGFM.SUM_QH.name]
               / (segments[SEGFM.DTLN.name] * 0.8)).sum()

    # number of exchangers
    ha, ca, hb, cb = pinch_streams_tables(hot, cold, dt, pinch, hot_coefs,
                                          cold_coefs)
    na = calculate_minimum_exchangers(ha, ca, 'above')
    nb = calculate_minimum_exchangers(hb, cb, 'below')
    n_ex = na + nb

    # area per exchanger
    area = netarea / n_ex

    # bare module cost
    index_ratio = 542 / 397  # CEPCI index
    cbm = calculate_bare_module_cost(extype, arrangement, shell_mat, tube_mat,
                                     area, pressure) * index_ratio

    # utilities costs
    h_price = 9.830  # $/GJ
    c_price = 0.353  # $/GJ
    huc = huq * 1e3 * 3600 * 8000 * h_price * 1e-9
    cuc = cuq * 1e3 * 3600 * 8000 * c_price * 1e-9

    # compound cost
    n = 5  # years
    i = 0.1  # % per year (before tax)
    cc = (i * (1 + i) ** n) / ((1 + i) ** n - 1)

    # final eaoc
    eaoc = cc * n_ex * cbm + huc + cuc

    return eaoc, netarea, huq, cuq, n_ex
