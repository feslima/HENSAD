from PyQt5.uic import compileUi
import pathlib

view_folder = pathlib.Path(__file__).absolute().parent
ui_folder = pathlib.Path(view_folder / 'ui')
py_folder = pathlib.Path(view_folder / 'py')

# compile the files from the ui_files folder to the py_folder
for uifile in sorted(ui_folder.glob('*.ui')):
    pyfp = (py_folder / uifile.stem).with_suffix('.py').open("w",
                                                             encoding="utf-8")
    compileUi(str(uifile), pyfp, from_imports=True,
              import_from='gui.resources')
    pyfp.close()
