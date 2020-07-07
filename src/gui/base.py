import logging
import sys
import traceback

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox

logging.basicConfig(filename='HENSAD.log', filemode='w',
                    level=logging.CRITICAL)


def my_exception_hook(exctype, value, tback):
    """Exception hook to catch exceptions from PyQt and show the error message
    as a dialog box.
    """
    str_error_msg = ''.join(traceback.format_exception(exctype, value, tback))

    # Show the dialog
    user_msg = """
    The application crashed and will be closed.

    If you wish, a log of the crash can be found in the application folder 
    under the name 'HENSAD.log'.

    To report this, you can open an issue on the HENSAD Github repository and 
    upload the log file contents so you can help us to fix this problem.
    """
    error_dialog = QMessageBox(
        QMessageBox.Critical,
        "HENSAD critical error!",
        user_msg,
        QMessageBox.Save | QMessageBox.Discard,
        None,
        Qt.Dialog | Qt.MSWindowsFixedSizeDialogHint
    )
    error_dialog.setDefaultButton(QMessageBox.Save)

    save_button = error_dialog.button(QMessageBox.Save)
    save_button.setText("Save log file")

    ret = error_dialog.exec_()

    if ret == QMessageBox.Save:
        # Log the error
        logging.critical(str_error_msg)

    # Call the normal Exception hook after
    sys.__excepthook__(exctype, value, tback)

    # exit the application to avoid weird behavior
    sys.exit(1)
