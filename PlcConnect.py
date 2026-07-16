# This Python file uses the following encoding: utf-8

import sys
import snap7
from snap7.util import get_word, get_dword, get_int, get_dint
from snap7.type import Areas
from PySide6 import QtWidgets
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QApplication, QWidget, QLineEdit, QVBoxLayout

class PlcConnect(QtWidgets.QWidget):
    def __init__(self, parent_widget):
        self.ui = parent_widget
        self.plc = snap7.client.Client()
        self.init_validator()
        self.temp_meters = None
        self.zero_crossing = None
        self.meters = None

    def init_validator(self):
        # Wyrażenie regularne do walidacji adresu IP
        ip_range = r"(?:[0-1]?[0-9]?[0-9]|2[0-4][0-9]|25[0-5])"
        ip_regex = r"^" + ip_range + r"(?:\." + ip_range + r"){3}$"

        # Tworzymy QRegularExpression z wyrażeniem regularnym
        regex = QRegularExpression(ip_regex)

        # Tworzymy walidator
        validator = QRegularExpressionValidator(regex)  # Użyj 'self' jako rodzica

        # Ustawiamy walidator i maskę wejściową
        self.ui.PlcAdressEdit.setValidator(validator)
        self.ui.PlcAdressEdit.setInputMask("000.000.000.000")  # Ustawienie maski wejściowej

        # Ustawienie domyślnego tekstu
        self.ui.PlcAdressEdit.setText("172.022.001.040")

    def connect_plc(self):
        ret = False
        #próba połączenia z plc
        plc_ip = self.ui.PlcAdressEdit.text() #adress plc
        #usunięcie niepotrzebnych zer
        # Podział adresu IP na oktety
        octets = plc_ip.split('.')#podział adresu na tblicę
        octets = [str(int(octet)) for octet in octets]#literacja po tablicy, zamiana na int i nastepnie z int na string
        normalized_plc_ip = '.'.join(octets)#połacznie tablicy w ciag znaków

        rack = self.ui.PlcRackBox.value()
        slot = self.ui.PlcSlotBox.value()

        try:
            if not self.plc.get_connected():
                self.temp_meters = 0;
                self.zero_crossing = False
                self.plc.connect(normalized_plc_ip, rack, slot)

            if self.plc.get_connected():
                print("Połączono z plc")
                ret = True
            else:
                print("Błąd połączenia z plc")

        except Exception as e:
            #self.ui.label_fault.setText(f"Błąd połączenia: {e}")
            print(f"Błąd połączenia z plc: {e}")

        return ret

    def read_plc_data(self, db_number, vlaue_offset, value_size_index):
        ret = False
        data_value = 0
        #ustawienie długości/zakresu zmiennej
        if value_size_index in [0, 2]:
            value_size = 2
        elif value_size_index in [1, 3]:
            value_size = 4
        else:
            value_size = 2
        #próba odczytania zmiennej
        try:
            data_plc = self.plc.read_area(Areas.DB, db_number, vlaue_offset, value_size)
            #formatowanie zmiennej po rozmiarze
            if value_size_index == 0:
                data_value = get_word(data_plc, 0)
            elif value_size_index == 1:
                data_value = get_dword(data_plc, 0)
            elif value_size_index == 2:
                data_value = get_int(data_plc, 0)
            elif value_size_index == 3:
                data_value = get_dint(data_plc, 0)
            else:
                data_value = 0
            #self.label_fault.setText(f"Wartość DWord: {data_value}")
            #data_value = get_int(data_plc, 0)
            print(f"Wartość: {data_value}")
            ret = True
        except Exception as e:
            #self.label_fault.setText(f"Błąd odczytu: {e}")
            print(f"Błąd odczytu: {e}")

        return ret, data_value

    def read_plc(self):
        ret = False
        #sprawdzenie połącznia
        if not self.plc.get_connected():
            ret = self.connect_plc()#próba ponownaego połącznia
        else:
            ret = True
        #odczyt zmiennych jeśli połaczono
        if ret == True: #self.plc.get_connected():
            #odczyt licznika metrów
            db_number_counter = self.ui.PlcDBCounteBox.value()#numer db aktualny metr
            offset_address_counter = self.ui.PlcOffsetCounterBox.value()#offset zmiennej
            value_size_counter = self.ui.PlcTypeCounterNrBox.currentIndex()  #zakres zmiennej
            ret, self.meters = self.read_plc_data(db_number_counter, offset_address_counter, value_size_counter)
            if ret == True :
                #self.ui.CountEdit.setText(str(meters/10))
                self.ui.CountEdit.setText(f"{self.meters / 10:.0f}")
                if(self.meters < self.temp_meters and self.zero_crossing == False):
                    self.zero_crossing = True
                self.temp_meters = self.meters
                #if(self.zero_crossing == True and self.meters > 0): #przeniesione do klasy bazowej widget.py
                    #self.zero_crossing = False
            #odczyt biezącej prędkości
            db_number_speed = self.ui.PlcDBSpeedBox.value()#numer db aktualna predkość
            offset_address_speed = self.ui.PlcOffsetSpeedBox.value()#offset zmiennej
            value_size_speed = self.ui.PlcTypeSpeedNrBox.currentIndex()  #zakres zmiennej
            ret, speed = self.read_plc_data(db_number_speed, offset_address_speed, value_size_speed)
            if ret == True :
                speed = (speed - self.ui.OffsetSpeedBox.value()) * self.ui.MulSpeedBox.value()
                if speed < 0:
                    speed = 0
                self.ui.SpeedEdit.setText(str(speed))



    def closeEvent(self, event):
        #rozłączenie przy zamykaniu jeśli połaczono
        if self.plc.get_connected():
            self.plc.disconnect()
        event.accept()
