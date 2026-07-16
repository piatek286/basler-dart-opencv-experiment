# This Python file uses the following encoding: utf-8
import sys
#import pytesseract
from filters import Filters  # Import klasy VideoProcessor
from basler import BaslerCapture
from PlcConnect import PlcConnect
from DisplayAnalizeBox import DisplayAnalizeBox


from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget
#from PySide6.QtWidgets import QListWidget, QListWidgetItem
from PySide6.QtWidgets import QSlider, QSpinBox, QComboBox, QCheckBox, QDoubleSpinBox, QLineEdit
from PySide6.QtCore import QObject

# Important:
# You need to run the following command to generate the ui_form.py file
#     pyside6-uic form.ui -o ui_form.py, or
#     pyside2-uic form.ui -o ui_form.py
from ui_form import Ui_Widget

from PySide6.QtWidgets import QFileDialog
import os
settings_folder_path = "program settings"
filename_settings = "settings.txt"
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

#klasa obsługi okna
class Widget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Widget()
        self.ui.setupUi(self)
        self.main()
        self.loading_settings = False#flaga przeładowanie wartości z pliku recept


    def main(self):
        self.label_camera = self.ui.label_camera
        self.label_image = self.ui.label_image
        #odczyt ustawień
        self.read_settings_file()
        #inicjalizacja klasy plc
        self.plc = PlcConnect(self.ui)
        #self.plc.read_plc()
        self.plc_read_timer = QTimer(self)
        self.plc_read_timer.timeout.connect(self.plc.read_plc)
        #self.plc_read_timer_connect()

        #obiekt dostepu do kamer
        self.camera = None
        self.basler = BaslerCapture(self.ui, QTimer)
        #self.slider_timer = QTimer(self)

        #numer wybranej kamery, default 0, zwykła kamera usb
        #self.capture = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        #funkcje podmiany na basler
        self.cap_filters = Filters(self.ui)#, self.basler)
        #self.cap_filters = Filters(self.ui, self.basler)
        #timer wywołania funkcji obrazu
        self.timer = QTimer(self)
        self.analize_timer = QTimer(self)
        self.timer.timeout.connect(self.cap_filters.update_orginal_frame)
        #self.analize_timer.timeout.connect(self.cap_filters.update_analize)#zaloncznie analizy obrazu
        self.analize_timer.timeout.connect(self.analize_timer_count)
        #sloty
        #sloty do przycisków
        self.ui.ConnectPlcButton.clicked.connect(self.plc_read_timer_connect)
        self.ui.StartButton.clicked.connect(self.start_camera)
        self.ui.StopButton.clicked.connect(self.stop_camera)
        #self.ui.TakeButton.clicked.connect(self.changeCursor)
        #self.ui.ResetFilterButton.clicked.connect(self.reset_filter)
        #slot pobranie koloru
        #self.ui.label_camera.mousePressEvent = self.get_color_from_click
        #sloty dla zakładki detekcji uszkodzeń
        #self.ui.TakeDimButton.clicked.connect(self.take_dimmeter)
        #self.ui.AutoDistanceButton.clicked.connect(self.set_lines)
        #slot do zmiany czestotliwosci analizy
        self.ui.AproxBox.clicked.connect(self.analize_timer_count)
        #otwarcie kamery
        self.ui.ConnectButton.clicked.connect(self.open_cam)
        #zamknięcie połączenia
        self.ui.DisconnectButton.clicked.connect(self.close_cam)
        #zapis ustawień
        self.ui.WtiteSettingsButton.clicked.connect(self.write_recipes)
        #odczyt ustawień
        self.ui.ReadSettingsButton.clicked.connect(self.read_recipes)
        #czekbox okinka analizy sloty/syganaly przeloncznie
        self.slots_box_display_analize = DisplayAnalizeBox(self.ui)

        #wylocznie zakładek przed załączniem kamery
        #self.ui.SettingsWidget.setTabEnabled(1, False)
        #self.ui.SettingsWidget.setTabEnabled(2, False)
        #self.ui.SettingsWidget.setTabEnabled(3, False)

    #odczytanie pliku stawień programu
    def read_settings_file(self):
        #odczyt pliku konfiguracyjnego
        #if not os.path.exists(settings_folder_path):
            #os.makedirs(settings_folder_path)#jeżeli folder nie istnieje to go tworzy
        file_path_settings = os.path.join(settings_folder_path, f"{filename_settings}") #dodanie do ścieżki nazwy pliku
        # Sprawdzenie, czy plik istnieje i odczytanie pierwszej linijki
        if os.path.exists(file_path_settings):
            with open(file_path_settings, "r", encoding="utf-8") as f:
                folder_path_recip = f.readline().strip()
                print("Foldr recept", folder_path_recip)
                file_name_recipe = f.readline().strip()
                print("Ostatnia recepta", file_name_recipe)
                if os.path.exists(file_name_recipe):
                    with open(file_name_recipe, "r", encoding="utf-8") as f:
                        print("Otwarcie pliku:", file_name_recipe)
                        self.read_recipe_file(f)
                else:
                    print("Plik z receptą nie istnieje:", file_name_recipe)

        else:
            print("Plik nie istnieje:", file_path_settings)

    #zapis recepty
    def write_recipe_file(self, file):
        widget_types = [
            (QSlider, "QSlider_", lambda w: w.value()),
            (QSpinBox, "QSpinBox_", lambda w: w.value()),
            (QComboBox, "QComboBox_", lambda w: w.currentIndex()),
            (QCheckBox, "QCheckBox_", lambda w: int(w.isChecked())),
            (QDoubleSpinBox, "QDoubleSpinBox_", lambda w: w.value()),
            (QLineEdit, "QLineEdit_", lambda w: w.text() if w.text() else "-"),
        ]

        for i in range(self.ui.SettingsWidget.count()):#literacja po zakładkach
            tab_name = self.ui.SettingsWidget.tabText(i)#pobranie nazwy
            file.write(f"QWidget_{tab_name}:\n")#zapis nagłówka do pliku
            tab = self.ui.SettingsWidget.widget(i)#tabela typów w zakładce

            for widget_class, prefix, get_value in widget_types:#litaracja po typach
                widgets = tab.findChildren(widget_class)#pobranie obiektu po typie klasy
                if widget_class == QLineEdit:#dla obiektu typu QLineEdit
                    # Pomijamy QLineEdit z nazwą qt_spinbox_lineedit
                    widgets = [w for w in widgets if w.objectName() != "qt_spinbox_lineedit"]#pomijanie niechcianych wartości

                for widget in widgets:#literacja po kazdym obiekcie z danj klasy
                    name = widget.objectName()#pobranie nazwy
                    value = get_value(widget)#pobranie wartosci
                    if value is None:
                        value = 0
                    file.write(f"{prefix}{name}={value}\n")#zapis do pliku

    def write_recipes(self):
        file_path_settings = os.path.join(settings_folder_path, f"{filename_settings}")
        first_line = ""
        if os.path.exists(file_path_settings):
            with open(file_path_settings, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                print("Foldr recept", first_line)
        else:
            first_line = "~" # domyślny katalog (np. Pulpit/Dokumenty)
            print("Plik nie istnieje:", file_path_settings)

        # Wyświetlenie okna dialogowego "Zapisz jako"
        file_path_recipe, _ = QFileDialog.getSaveFileName(
            self,
            "Zapisz plik jako",
            os.path.expanduser(first_line),
            "Pliki tekstowe (*.txt);;Wszystkie pliki (*)"
        )

        if file_path_recipe:
            # Zapis danych do pliku
            with open(file_path_recipe, "w", encoding="utf-8") as f:
                #zapis ustawień elementów GUI
                self.write_recipe_file(f)
                #zapis w ustawieniach głównych ostatniej recepty
                file_path_settings = os.path.join(settings_folder_path, f"{filename_settings}")
                if os.path.exists(file_path_settings):
                    with open(file_path_settings, "w", encoding="utf-8") as f_settings:
                        folder_path = os.path.dirname(file_path_recipe)
                        f_settings.write(folder_path + "\n")
                        f_settings.write(file_path_recipe + "\n")
                        print("Zapis scieżki ostaniej recepty")
                else:
                    print("Plik ustawien nie istnieje:", file_path_settings)
            print("Zapisano plik:", file_path_recipe)
        else:
            print("Anulowano zapis pliku.")

    #odczyt recepty
    def read_recipe_file(self, file):
        current_tab = None
        for line in file:
            line = line.strip()
            if not line:
                continue
            if line.startswith("QWidget_"):
                # Linia z nazwą zakładki
                tab_name = line[len("QWidget_"):].rstrip(':')
                # Znajdujemy zakładkę o tej nazwie
                for i in range(self.ui.SettingsWidget.count()):
                    if self.ui.SettingsWidget.tabText(i) == tab_name:
                        current_tab = self.ui.SettingsWidget.widget(i)
                        break
            else:
                if current_tab is None:
                    continue  # pomijamy jeśli nie mamy zakładki
                # Format linii: TypWidget_Nazwa=wartość
                try:
                    type_and_name, value = line.split('=', 1)
                    widget_type, name = type_and_name.split('_', 1)
                except ValueError:
                    continue  # linia źle sformatowana, pomijamy

                # Szukamy widgetu po nazwie
                widget = current_tab.findChild(QObject, name)
                if widget is None:
                    continue  # widget o takiej nazwie nie istnieje, pomijamy

                # Ustawiamy wartość zależnie od typu widgetu
                if widget_type == "QSlider":
                    widget.setValue(int(value))
                elif widget_type == "QSpinBox":
                    widget.setValue(int(value))
                elif widget_type == "QComboBox":
                    widget.setCurrentIndex(int(value))
                elif widget_type == "QCheckBox":
                    widget.setChecked(value == 'True' or value == '1')
                elif widget_type == "QDoubleSpinBox":
                    widget.setValue(float(value))
                elif widget_type == "QLineEdit":
                    if value == '-':
                        value = ""
                    widget.setText(value)

    def read_recipes(self):
        self.loading_settings = True
        file_path_settings = os.path.join(settings_folder_path, f"{filename_settings}") #dodanie do ścieżki nazwy pliku
        # Sprawdzenie, czy plik istnieje i odczytanie pierwszej linijki
        first_line = ""
        if os.path.exists(file_path_settings):
            with open(file_path_settings, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                print("Foldr recept", first_line)
        else:
            first_line = "~"  # domyślny katalog
            print("Plik nie istnieje:", file_path_settings)

        file_path_recipe, _ = QFileDialog.getOpenFileName(
            self,
            "Otwórz plik",
            os.path.expanduser(first_line),
            "Pliki tekstowe (*.txt);;Wszystkie pliki (*)"
        )
        if file_path_recipe:
            with open(file_path_recipe, "r", encoding="utf-8") as f:
                print("Otwarcie pliku:", file_path_recipe)
                self.read_recipe_file(f)
        else:
            print("Anulowano otwarcie pliku.")
        self.loading_settings = False


# wywaołanie cyklicznego odczytu plc
    def plc_read_timer_connect (self):
        ret_plc_connect = self.plc.connect_plc()
        if ret_plc_connect == True:
            self.plc_read_timer.start(250)
            self.ui.StausPlcLabel.setText("Plc satus: połączono")
            self.ui.PlcUseCheckBox.setCheckState(Qt.Checked)
        else:
            self.plc_read_timer.stop()
            self.ui.StausPlcLabel.setText("Plc satus: błąd połączenia")
            self.ui.PlcUseCheckBox.setCheckState(Qt.Unchecked)
            self.analize_timer_count()

# zmina czasu analizy
    def analize_timer_count(self):
        width_window = self.ui.AnalizemmBox.value()
        if self.ui.AproxBox.isChecked():
            if not self.ui.PlcUseCheckBox.isChecked():#oblicznie na podstawie wprowadzonych danych
                #oblicznie klatek na podstawie prędkości dla predkości analizy
                #T[ms] = (szerokosc[mm] * 60) / predkosc[m/min]
                delay = (width_window * 60) / self.ui.SpeedBox.value()
                fps = 1000/delay
                self.ui.FpsLineEdit.setText(f"{fps:.0f}")
                self.analize_timer.start(delay)
            else:#oblicznie na podstawie prędkości z plc
                speed = int(float(self.ui.SpeedEdit.text()))
                if speed < 1 :
                    speed = 1
                delay = (width_window * 60) / speed
                fps = 1000/delay
                self.ui.FpsLinePlcEdit.setText(f"{fps:.1f}")
                self.analize_timer.start(delay)
                if(self.zero_crossing == True and self.meters > 0):#wywołnie utworzenia nowego folderu z datą
                    self.zero_crossing = False
                    self.cap_filters.folder_create()

#otwarcie kamery
    def set_camera(self):
        ret = self.basler.open_camera_with_resolution()
        return ret

    def open_cam(self):
        ret = self.set_camera()
        if ret:
            #załącznie wyloncznie funkcji interfejsu
            self.ui.CamWidthSlider.setEnabled(False)
            self.ui.CamWidthBox.setEnabled(False)
            self.ui.CamHighSlider.setEnabled(False)
            self.ui.CamHighBox.setEnabled(False)
            self.ui.CamBinningComboBox.setEnabled(False)
            self.ui.CamFormatComboBox.setEnabled(False)
            self.ui.CamFpsBox.setEnabled(False)
            self.ui.CamNrComboBox.setEnabled(False)
            self.ui.RefreshCamButton.setEnabled(False)
            self.ui.ConnectButton.setEnabled(False)
            self.ui.ReadSettingsButton.setEnabled(False)
            self.ui.DisconnectButton.setEnabled(True)
            self.ui.StartButton.setEnabled(True)

    def close_cam(self):
        self.basler.disconnect()
        #załącznie wyloncznie funkcji interfejsu
        self.ui.CamWidthSlider.setEnabled(True)
        self.ui.CamWidthBox.setEnabled(True)
        self.ui.CamHighSlider.setEnabled(True)
        self.ui.CamHighBox.setEnabled(True)
        self.ui.CamBinningComboBox.setEnabled(True)
        self.ui.CamFormatComboBox.setEnabled(True)
        self.ui.CamFpsBox.setEnabled(True)
        self.ui.CamNrComboBox.setEnabled(True)
        self.ui.RefreshCamButton.setEnabled(True)
        self.ui.ConnectButton.setEnabled(True)

        self.ui.DisconnectButton.setEnabled(False)
        self.ui.StartButton.setEnabled(False)
        self.ui.ReadSettingsButton.setEnabled(True)

    #załącznie przechwytywania obrazu
    def start_camera(self):
        ret = self.basler.start_grabing()
        if ret:
            self.cap_filters.folder_create()
            self.ui.StartButton.setEnabled(False)
            self.ui.DisconnectButton.setEnabled(False)
            self.ui.StopButton.setEnabled(True)
            self.ui.SettingsWidget.setTabEnabled(1, True)
            self.ui.SettingsWidget.setTabEnabled(2, True)
            self.ui.SettingsWidget.setTabEnabled(3, True)
            #self.ui.CamOffsetXSlider.setEnabled(True)
            #self.ui.CamOffsetXBox.setEnabled(True)
            #self.ui.CamOffsetYSlider.setEnabled(True)
            #self.ui.CamOffsetYBox.setEnabled(True)
            self.ui.CenterXYButton.setEnabled(True)
            self.cap_filters.set_capture(self.basler)
            self.timer.start(30)#wyświetlanie obrazu orginalnego
            self.analize_timer.start(30)
            self.cap_filters.start_threads()
            if self.ui.PlcUseCheckBox.isChecked():
                self.plc_read_timer_connect()
        else:#błąd kamery
            self.close_cam()

    def stop_camera(self):
        self.timer.stop()
        self.analize_timer.stop()
        self.cap_filters.stop_threads()
        self.ui.StartButton.setEnabled(True)
        self.ui.DisconnectButton.setEnabled(True)
        self.ui.StopButton.setEnabled(False)
        self.ui.SettingsWidget.setTabEnabled(1, False)
        self.ui.SettingsWidget.setTabEnabled(2, False)
        self.ui.SettingsWidget.setTabEnabled(3, False)
        #self.ui.CamOffsetXSlider.setEnabled(False)
        #self.ui.CamOffsetXBox.setEnabled(False)
        #self.ui.CamOffsetYSlider.setEnabled(False)
        #self.ui.CamOffsetYBox.setEnabled(False)
        #self.ui.CenterXYButton.setEnabled(False)
        #self.basler.disconnect()
        self.basler.release()
        #self.label_camera.clear()#czyszczenie obrazu z kamery

    def closeEvent(self, event):
        #self.capture.release()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = Widget()
    widget.show()
    sys.exit(app.exec())
