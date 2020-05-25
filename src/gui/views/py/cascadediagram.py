# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'C:\Users\Felipe\hensad\src\gui\views\ui\cascadediagram.ui'
#
# Created by: PyQt5 UI code generator 5.14.2
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(1024, 800)
        Dialog.setMinimumSize(QtCore.QSize(1024, 800))
        self.gridLayout = QtWidgets.QGridLayout(Dialog)
        self.gridLayout.setObjectName("gridLayout")
        self.approachTempHorizontalSlider = QtWidgets.QSlider(Dialog)
        self.approachTempHorizontalSlider.setMinimum(5)
        self.approachTempHorizontalSlider.setMaximum(30)
        self.approachTempHorizontalSlider.setSingleStep(2)
        self.approachTempHorizontalSlider.setProperty("value", 10)
        self.approachTempHorizontalSlider.setOrientation(QtCore.Qt.Horizontal)
        self.approachTempHorizontalSlider.setObjectName("approachTempHorizontalSlider")
        self.gridLayout.addWidget(self.approachTempHorizontalSlider, 0, 0, 1, 1)
        self.cascadeDiagramGraphicsView = QtWidgets.QGraphicsView(Dialog)
        self.cascadeDiagramGraphicsView.setObjectName("cascadeDiagramGraphicsView")
        self.gridLayout.addWidget(self.cascadeDiagramGraphicsView, 1, 0, 1, 1)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Dialog"))
