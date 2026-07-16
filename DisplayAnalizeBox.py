# This Python file uses the following encoding: utf-8

from PySide6 import QtWidgets
from PySide6.QtWidgets import QCheckBox
from PySide6.QtCore import Qt


class DisplayAnalizeBox(QtWidgets.QWidget):
    def __init__(self, parent_widget):
        self.ui = parent_widget
        self.checkboxes = self.ui.DisplayAnalizeFrame.findChildren(QCheckBox)

        #automatyczne przypisanie slot do każdego CheckBoxa
        for checkbox in self.checkboxes:#literacja po każdym elemencie
            checkbox.stateChanged.connect(lambda state, cb=checkbox: self.on_state_changed(state, cb))#cb kopia referncyjna aktualnie literowanego checkbox

    #slot wywołany zaznaczniem jednego z checkbox
    def on_state_changed(self, state, checkbox):
        checkbox_name = checkbox.text()
        if state == Qt.CheckState.Checked.value:
            for checkbox in self.checkboxes:
                if checkbox.text() != checkbox_name:#jeżeli nazwa różna od zanaczonego odznacz
                    checkbox.setChecked(False)
