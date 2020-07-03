# import line_profiler
import json
import numpy as np
import pandas as pd
import sys
import pathlib

MODFOLDER = pathlib.Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(MODFOLDER))

from hensad import ExchangerType, ArrangementType, MaterialType, calculate_eaoc  # noqa

# from pyinstrument import Profiler
# profile = line_profiler.LineProfiler()

# @profile


def main():
    fp = str(pathlib.Path(__file__).resolve().parent / "hsdtest.hsd")
    with open(fp, 'r') as f:
        hsd = json.load(f)

    hot = pd.DataFrame(hsd['hot'])
    hot.index = hot.index.astype(int)
    cold = pd.DataFrame(hsd['cold'])
    cold.index = cold.index.astype(int)

    hot_film = pd.DataFrame(hsd['hot_film'])
    hot_film.index = hot_film.index.astype(int)
    cold_film = pd.DataFrame(hsd['cold_film'])
    cold_film.index = cold_film.index.astype(int)

    new_rows = []

    DTMIN = 5
    DTMAX = 55
    PTS = np.linspace(DTMIN, DTMAX, 20, dtype=float)
    # profiler = Profiler()
    # profiler.start()

    for dt in PTS:
        eaoc, netarea, huq, cuq, n_ex = calculate_eaoc(
            hot, cold, dt,
            hot_film, cold_film,
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

    df = pd.concat([pd.DataFrame(row) for row in new_rows], ignore_index=True)
    print(df)
    # profiler.stop()

    # print(profiler.output_text(unicode=True, color=True, show_all=True))


if __name__ == "__main__":
    main()
