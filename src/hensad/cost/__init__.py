import pathlib
from enum import Enum, unique
from typing import List, Tuple

import numpy as np
import pandas as pd

_FOLDERPATH = pathlib.Path(__file__).resolve().parent


COST_DATA = pd.read_csv(
    _FOLDERPATH / 'heat_exchanger.csv',
    index_col=['TYPE', 'ARRANGEMENT', 'PRESSURE']
).sort_index()

MATERIAL_DATA = pd.read_csv(
    _FOLDERPATH / 'heat_ex_mat_fac.csv',
    index_col=['TYPE', 'SHELL', 'TUBE']
).sort_index()


class TypeBaseEnum(Enum):
    @classmethod
    def values_list(cls) -> List[str]:
        return list(map(lambda c: c.value, cls))


@unique
class ExchangerType(TypeBaseEnum):
    AIR_COOLER = 'Air cooler'
    BAYONET = 'Bayonet'
    DOUBLE_PIPE = 'Double pipe'
    FIXED_TUBE = 'Fixed tube'
    FLAT_PLATE = 'Flat plate'
    FLOATING_HEAD = 'Floating head'
    KETTLE_REBOILER = 'Kettle reboiler'
    MULTIPLE_PIPE = 'Multiple pipe'
    SCRAPED_WALL = 'Scraped wall'
    SPIRAL_PLATE = 'Spiral plate'
    SPIRAL_TUBE = 'Spiral tube'
    TEFLON_TUBE = 'Teflon tube'
    U_TUBE = 'U tube'


@unique
class ArrangementType(TypeBaseEnum):
    CONVENTIONAL = 'Conventional'
    SHELL_TUBE = 'Shell & Tube'
    TUBE_ONLY = 'Tube only'


@unique
class PressureType(TypeBaseEnum):
    HIGH = 'High'
    LOW = 'Low'
    MEDIUM = 'Medium'


@unique
class MaterialType(TypeBaseEnum):
    CS = 'Carbon Steel'
    SS = 'Stainless Steel'
    Cu = 'Copper'
    Ni = 'Nickel'
    Ti = 'Titanium'
    Al = 'Aluminum'
    NONE = np.NaN


def _calculate_property(prop: float, c1: float, c2: float, c3: float) -> float:
    """Calculates either purchase cost or pressure factor based on the equation

    result = 10 ^ (c1 + c2 * log10(prop) c3 * log10(prop) ^ 2)

    Parameters
    ----------
    prop : float
        Either area or pressure value.
    c1 : float
        First constant.
    c2 : float
        Second constant.
    c3 : float
        Third constant.

    Returns
    -------
    float
        calculated purchase cost or pressure factor.
    """
    return 10 ** (c1 + c2 * np.log10(prop) + c3 * np.log10(prop) ** 2).item()


def _get_exchanger_data(ex: ExchangerType, arrangement: ArrangementType,
                        area: float, pressure: float) -> pd.DataFrame:
    # checks inputs and returns the heat exchanger data
    try:
        exdata = COST_DATA.loc[(ex.value, arrangement.value), :]
    except KeyError as e:
        err_msg = ("No data for '{0}' heat exchanger with "
                   "'{1}' tube arrangement.")
        raise ValueError(err_msg.format(ex.value, arrangement.value))

    plimits = exdata.loc[:, ['PMIN', 'PMAX']]
    pmin = plimits['PMIN'].min()
    pmax = plimits['PMAX'].max()

    if pressure < pmin or pressure > pmax:
        raise ValueError("Pressure outside allowed range.")

    for pidx, limit in plimits.iterrows():
        interval = pd.Interval(limit['PMIN'], limit['PMAX'], closed='left')
        if pressure in interval:
            ptype = PressureType(pidx)
            break

    exdata = COST_DATA.loc[(ex.value, arrangement.value, ptype.value), :]
    amin, amax = exdata.loc[['AMIN', 'AMAX']]

    if area < amin or area > amax:
        raise ValueError("Area outside allowed range.")

    return exdata


def _get_material_data(ex: ExchangerType, shell_mat: MaterialType,
                       tube_mat: MaterialType) -> float:
    # checks inputs and returns the material factor
    try:
        fm = MATERIAL_DATA.loc[
            (ex.value, shell_mat.value, tube_mat.value),
            'FM'
        ].item()
    except KeyError as e:
        err_msg = ("No data for '{0}' exchanger with '{1}' as shell side "
                   "and '{2}' as tube side material.")

        ex = ex.value

        if not np.isnan(shell_mat.value):
            shell_mat = shell_mat.value
        else:
            shell_mat = 'None'

        if not np.isnan(tube_mat.value):
            tube_mat = tube_mat.value
        else:
            tube_mat = 'None'

        raise ValueError(err_msg.format(ex, shell_mat, tube_mat))

    return fm


def _calculate_cp0(area: float, exdata: pd.DataFrame) -> float:
    k1, k2, k3 = exdata.loc[['K1', 'K2', 'K3']]

    return _calculate_property(area, k1, k2, k3)


def _calculate_fp(pressure: float, exdata: pd.DataFrame) -> float:
    c1, c2, c3 = exdata.loc[['C1', 'C2', 'C3']]

    return _calculate_property(pressure, c1, c2, c3)


def calculate_purchase_cost(ex: ExchangerType, arrangement: ArrangementType,
                            area: float, pressure: float) -> float:
    exdata = _get_exchanger_data(ex, arrangement, area, pressure)

    return _calculate_cp0(area, exdata)


def calculate_pressure_factor(ex: ExchangerType, arrangement: ArrangementType,
                              area: float, pressure: float) -> float:
    exdata = _get_exchanger_data(ex, arrangement, area, pressure)

    return _calculate_fp(pressure, exdata)

def calculate_bare_module_cost(ex: ExchangerType, arrangement: ArrangementType,
                               shell_mat: MaterialType, tube_mat: MaterialType,
                               area: float, pressure: float) -> float:
    """Calculates the bare module cost (CTM) for a heat exchanger based on tube
    'arrangement', shell ('shell_mat') and tube ('tube_mat') side materials, 
    'area' of heat exchange and operation 'pressure'.

    Parameters
    ----------
    ex : ExchangerType
        Type of heat exchanger. See ExchangerType enumerator for possible
        exchangers.
    arrangement : ArrangementType
        Type of tube arrangement. See ArrangementType enumerator for possible
        arrangements.
    shell_mat : MaterialType
        Shell side material.
    tube_mat : MaterialType
        Tube side material.
    area : float
        Area of heat exchange.
    pressure : float
        Pressure of operation.

    Returns
    -------
    float
        Bare module cost (CTM) for a heat exchanger.
    """
    exdata = _get_exchanger_data(ex, arrangement, area, pressure)
    fm = _get_material_data(ex, shell_mat, tube_mat)

    cp0 = _calculate_cp0(area, exdata)
    fp = _calculate_fp(pressure, exdata)

    b1, b2 = exdata.loc[['B1', 'B2']]

    return cp0 * (b1 + b2 * fm * fp)
