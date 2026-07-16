# This Python file uses the following encoding: utf-8
from PySide6 import QtWidgets
from pypylon import pylon
from enum import Enum

import threading
import time

STEP = 4

class TypeChange(Enum):
    SLIDER = 1
    BOX = 2

class BinningValue(Enum):
    FULL = (1440, 1080)
    HALF = (720, 540)
    QUATER = (180, 135)

class BaslerCapture(QtWidgets.QWidget):
    def __init__(self, parent_widget, timer):
        super().__init__()
        self.ui = parent_widget
        self.camera = None
        self.capture = None
        self.timer = timer
        self.tl_factory = pylon.TlFactory.GetInstance()
        # blokada dla bezpiecznego dostępu do klatek
        self.lock = threading.Lock()
        # Wątek odczytu działa cały czas
        #wątek odczytu kamery
        self.event_read_cam = None
        self.stop_event = None
        #sloty podłączenie
        #self.slot_connect_after()
        #self.slot_connect_before()
        self.slot_connect()
        #pobranie listy kamer
        self.refresh_camera_list()
        #ustawnie max wartości dla sowakówi soinbox
        self.update_resolution_binning_max()

    def start_grabing(self):
        if self.camera is None:
            print("Brak kamery do uruchomienia")
            return False

        try:
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
        except Exception as e:
            print(f"Błąd otwarcia kamery: {e}")
            return False

        # Konwerter obrazu
        self.converter = pylon.ImageFormatConverter()
        self.converter.OutputPixelFormat = pylon.PixelType_BGR8packed
        self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

        # Tworzymy nowy wątek odczytu
        interwal = 0.01
        self.stop_event = threading.Event()
        self.event_read_cam = threading.Thread(
            target=self.read_event,
            args=(self.stop_event, interwal),
            daemon=True
        )
        self.event_read_cam.start()
        print("Wątek kamery uruchomiony")
        return True

    def read(self):
        with self.lock:
            return self.capture

    def read_cam(self):
        if self.camera.IsGrabbing():
            try:
                grabResult = self.camera.RetrieveResult(1000, pylon.TimeoutHandling_ThrowException)
            except Exception as e:
                print(f"Błąd pobrania obrazu z kamry: {e}")
                self.ui.StopButton.click()
                return False, None

            if grabResult.GrabSucceeded():
                image = self.converter.Convert(grabResult)
                frame = image.GetArray()
                grabResult.Release()
                return True, frame
        return False, None

    def read_event(self, stop_event, interwal):
        """Wątek do cyklicznego odczytu klatek"""
        next_time = time.perf_counter()
        while not stop_event.is_set():
            actual_time = time.perf_counter()
            if actual_time >= next_time:
                with self.lock:
                    self.capture = self.read_cam()
                next_time += interwal
            else:
                time.sleep(max(0, next_time - actual_time))

    def release(self):
        """Zatrzymanie wątku i kamery"""
        if self.stop_event and self.event_read_cam and self.event_read_cam.is_alive():
            self.stop_event.set()
            self.event_read_cam.join()
            print("Wątek kamery zakończony")

        if self.camera and self.camera.IsGrabbing():
            self.camera.StopGrabbing()

        # zwalniamy referencje
        self.event_read_cam = None
        self.stop_event = None


    def disconnect(self):
        self.release()
        if self.camera:
            self.camera.Close()

    #otwarcie kamery z ustawieniami
    def open_camera_with_resolution(self):
        cam_index = self.camera_chice()  # Pobranie indeksu wybranej kamery
        # Pobranie listy dostępnych kamer
        devices = self.tl_factory.EnumerateDevices()
        if cam_index >= len(devices):
            print(f"Nie można otworzyć kamery {cam_index}, brak urządzenia na tym indeksie.")
            return False
        # Zamknięcie poprzedniej kamery, jeśli była otwarta
        if self.camera is not None and self.camera.IsOpen():
            print("Zamykam wcześniej otwartą kamerę...")
            self.camera.Close()
            self.camera = None  # Usuwamy referencję do starej kamery
        # Tworzenie nowej instancji kamery
        self.camera = pylon.InstantCamera(self.tl_factory.CreateDevice(devices[cam_index]))
        try:
            self.camera.Open()
            print("Otwarto kamerę")
        except pylon.RuntimeException as e:
            print(f"Błąd otwierania kamery: {e}")
            self.camera = None  # W razie błędu usuwamy kamerę
            return False

        # ustawienie sumowania pikseli
        binning = self.ui.CamBinningComboBox.currentIndex()
        if binning == 0:
            self.camera.BinningSelector.Value = "Sensor"
            self.camera.BinningHorizontal.Value = 1
            self.camera.BinningVertical.Value = 1
        elif binning == 1:
            self.camera.BinningSelector.Value = "Sensor"
            self.camera.BinningHorizontal.Value = 2
            self.camera.BinningVertical.Value = 2
        elif binning == 2:
            self.camera.BinningSelector.Value = "Region1"
            self.camera.BinningHorizontalMode.Value = "Sum"
            self.camera.BinningVerticalMode.Value = "Sum"
            self.camera.BinningHorizontal.Value = 1
            self.camera.BinningVertical.Value = 1
        elif binning == 3:
            self.camera.BinningSelector.Value = "Region1"
            self.camera.BinningHorizontalMode.Value = "Average"
            self.camera.BinningVerticalMode.Value = "Average"
            self.camera.BinningHorizontal.Value = 1
            self.camera.BinningVertical.Value = 1
        elif binning == 4:
            self.camera.BinningSelector.Value = "Region1"
            self.camera.BinningHorizontalMode.Value = "Sum"
            self.camera.BinningVerticalMode.Value = "Sum"
            self.camera.BinningHorizontal.Value = 2
            self.camera.BinningVertical.Value = 2
        elif binning == 5:
            self.camera.BinningSelector.Value = "Region1"
            self.camera.BinningHorizontalMode.Value = "Average"
            self.camera.BinningVerticalMode.Value = "Average"
            self.camera.BinningHorizontal.Value = 2
            self.camera.BinningVertical.Value = 2
        elif binning == 6:
            self.camera.BinningSelector.Value = "Region1"
            self.camera.BinningHorizontalMode.Value = "Sum"
            self.camera.BinningVerticalMode.Value = "Sum"
            self.camera.BinningHorizontal.Value = 4
            self.camera.BinningVertical.Value = 4
        elif binning == 7:
            self.camera.BinningSelector.Value = "Region1"
            self.camera.BinningHorizontalMode.Value = "Average"
            self.camera.BinningVerticalMode.Value = "Average"
            self.camera.BinningHorizontal.Value = 4
            self.camera.BinningVertical.Value = 4

        #ustawienie rozdzielczości
        width = self.ui.CamWidthSlider.value()
        height = self.ui.CamHighSlider.value()
        self.camera.Width.Value = width
        self.camera.Height.Value = height
        self.camera.OffsetX.Value = 0
        self.camera.OffsetY.Value = 0

        # Ustawienie maksymalnego Fps dla kamery
        fps = self.ui.CamFpsBox.value()
        self.camera.AcquisitionFrameRateEnable.SetValue(True)
        self.camera.AcquisitionFrameRate.SetValue(fps)

        #format obrazu przesyłanego z kamery
        if self.ui.CamFormatComboBox.currentIndex() == 0:
            self.camera.PixelFormat.Value = "Mono8"
        elif self.ui.CamFormatComboBox.currentIndex() == 1:
            self.camera.PixelFormat.Value = "Mono12"
        else:
            self.camera.PixelFormat.Value = "Mono12p"

        #ustwienie czasu naświetlania
        self.camera.AutoExposureTimeLowerLimit.Value = 100#minLowerLimit
        self.camera.AutoExposureTimeUpperLimit.Value = 5000#maxUpperLimit
        #region wzmocnienia
        self.camera.GainSelector.Value = "All"
        #wczytanie ustawień ze sliderów
        self.set_analog_settings()

        #odczyt z kamery maksymalnego Fps obliczonego z ograniczeń wewnnętrznych
        self.read_cam_value()

        # Potwierdzenie ustawień
        print(f"Pomyślnie ustawiono kamerę na {self.camera.Width.Value}x{self.camera.Height.Value} px, {fps} FPS.")
        return True

#wybór kamery
    def camera_chice(self):
        index_cam = self.ui.CamNrComboBox.currentIndex()
        print(f"Wybrano kamerę: {index_cam}")
        return index_cam

#odświerzenie listy kamer
    def refresh_camera_list(self):
        """Odświeża listę dostępnych kamer i aktualizuje UI."""
        self.ui.CamNrComboBox.clear()  # Czyszczenie listy kamer

        try:
            self.ui.CamNrComboBox.currentIndexChanged.disconnect(self.camera_chice)
        except TypeError:
            pass  # Ignorujemy wyjątek, jeśli sygnał nie był podłączony

        try:
            devices = self.tl_factory.EnumerateDevices()  # Pobranie listy kamer
        except Exception as e:
            print(f"Błąd pobierania listy kamer: {e}")
            devices = []  # Jeśli wystąpił błąd, lista jest pusta

        if not devices:
            self.ui.CamNrComboBox.addItem("Brak kamer")
        else:
            for index, device in enumerate(devices):
                camera_name = f"{device.GetModelName()} (SN: {device.GetSerialNumber()})"
                self.ui.CamNrComboBox.addItem(camera_name)

        self.ui.CamNrComboBox.currentIndexChanged.connect(self.camera_chice)  # Ponowne podłączenie sygnału

#Funkcja odczytu wartości przeliczonych w kamerze dla ustawień
    def read_cam_value(self):
        #odczyt z kamery maksymalnego Fps obliczonego z ograniczeń wewnnętrznych
        real_max_fps = self.camera.BslResultingAcquisitionFrameRate.Value
        self.ui.CamMaxFpsEdit.setText(f"{real_max_fps:.1f}")
        #odczyt czasu odczytu matrycy
        sensor_read_time = self.camera.SensorReadoutTime.Value
        self.ui.CamCcdTimeEdit.setText(f"{sensor_read_time}")
        #odczyt czasu naswietlania
        sensor_exp_read_time = self.camera.BslExposureStartDelay.Value
        self.ui.CamExpTimeEdit.setText(f"{sensor_exp_read_time}")

#Sloty dla sliders i boxs dla ustawień kamery
    #def slot_connect_after(self):
    def slot_connect(self):
        #odświeżenie listy kamer
        self.ui.RefreshCamButton.clicked.connect(self.refresh_camera_list)
        #sloty dla listy rozwijanej
        self.ui.CamNrComboBox.currentIndexChanged.connect(self.camera_chice)

        self.ui.CamBinningComboBox.currentIndexChanged.connect(self.update_resolution_binning)
        self.ui.CamWidthSlider.valueChanged.connect(lambda _: self.update_resolution_settings(TypeChange.SLIDER))
        self.ui.CamHighSlider.valueChanged.connect(lambda _: self.update_resolution_settings(TypeChange.SLIDER))
        self.ui.CamWidthBox.valueChanged.connect(lambda _: self.update_resolution_settings(TypeChange.BOX))
        self.ui.CamHighBox.valueChanged.connect(lambda _: self.update_resolution_settings(TypeChange.BOX))

    #def slot_connect_before(self):
        self.ui.CamGainFuncComboBox.activated.connect(self.update_gain_func)
        self.ui.CamContrastTypeComboBox.currentIndexChanged.connect(self.chnge_contrast_type)
        self.ui.CamExpFuncComboBox.activated.connect(self.update_exp_func)
        self.ui.CenterXYButton.clicked.connect(self.set_ceter_xy)

        self.ui.CamBrightnessSlider.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.SLIDER))
        self.ui.CamContrastSlider.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.SLIDER))
        self.ui.CamGainSlider.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.SLIDER))
        self.ui.CamGammaSlider.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.SLIDER))
        self.ui.CamBlackLevelSlider.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.SLIDER))
        self.ui.CamExpSlider.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.SLIDER))
        self.ui.CamBrightnessBox.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.BOX))
        self.ui.CamContrastBox.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.BOX))
        self.ui.CamGainBox.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.BOX))
        self.ui.CamGammaBox.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.BOX))
        self.ui.CamBlackLevelBox.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.BOX))
        self.ui.CamExpBox.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.BOX))

        self.ui.CamOffsetXSlider.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.SLIDER))
        self.ui.CamOffsetYSlider.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.SLIDER))
        self.ui.CamOffsetXBox.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.BOX))
        self.ui.CamOffsetYBox.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.BOX))

        self.ui.FiltrSharpnessSlider.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.SLIDER))
        self.ui.FiltrNoiseSlider.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.SLIDER))
        self.ui.FiltrSharpnessBox.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.BOX))
        self.ui.FiltrNoiseBox.valueChanged.connect(lambda _: self.update_analog_settings(TypeChange.BOX))

#Funkcje dla slotów sliders i boxs dla ustawień kamery
    def update_resolution_binning_max(self):
        cam_binning = self.ui.CamBinningComboBox.currentIndex()
        if cam_binning == 0 or cam_binning == 2 or cam_binning == 3:
            self.ui.CamWidthSlider.setMaximum(BinningValue.FULL.value[0])
            self.ui.CamWidthBox.setMaximum(BinningValue.FULL.value[0])
            self.ui.CamHighSlider.setMaximum(BinningValue.FULL.value[1])
            self.ui.CamHighBox.setMaximum(BinningValue.FULL.value[1])
        elif cam_binning == 1 or cam_binning == 4 or cam_binning == 5:
            self.ui.CamWidthSlider.setMaximum(BinningValue.HALF.value[0])
            self.ui.CamWidthBox.setMaximum(BinningValue.HALF.value[0])
            self.ui.CamHighSlider.setMaximum(BinningValue.HALF.value[1])
            self.ui.CamHighBox.setMaximum(BinningValue.HALF.value[1])
        elif cam_binning == 6 or cam_binning == 7:
            self.ui.CamWidthSlider.setMaximum(BinningValue.QUATER.value[0])
            self.ui.CamWidthBox.setMaximum(BinningValue.QUATER.value[0])
            self.ui.CamHighSlider.setMaximum(BinningValue.QUATER.value[1])
            self.ui.CamHighBox.setMaximum(BinningValue.QUATER.value[1])

    def update_resolution_binning(self):
        self.update_resolution_binning_max()
        if getattr(self.ui, "loading_settings", False):
                    print("loading_settings =", getattr(self.main_window, "loading_settings", False))
                    return  # Ignorujemy zmiany przy ładowaniu

        cam_binning = self.ui.CamBinningComboBox.currentIndex()
        if cam_binning == 0 or cam_binning == 2 or cam_binning == 3:
            self.ui.CamWidthSlider.setValue(BinningValue.FULL.value[0])
            self.ui.CamWidthBox.setValue(BinningValue.FULL.value[0])
            self.ui.CamHighSlider.setValue(BinningValue.FULL.value[1])
            self.ui.CamHighBox.setValue(BinningValue.FULL.value[1])
        elif cam_binning == 1 or cam_binning == 4 or cam_binning == 5:
            self.ui.CamWidthSlider.setValue(BinningValue.HALF.value[0])
            self.ui.CamWidthBox.setValue(BinningValue.HALF.value[0])
            self.ui.CamHighSlider.setValue(BinningValue.HALF.value[1])
            self.ui.CamHighBox.setValue(BinningValue.HALF.value[1])
        elif cam_binning == 6 or cam_binning == 7:
            self.ui.CamWidthSlider.setValue(BinningValue.QUATER.value[0])
            self.ui.CamWidthBox.setValue(BinningValue.QUATER.value[0])
            self.ui.CamHighSlider.setValue(BinningValue.QUATER.value[1])
            self.ui.CamHighBox.setValue(BinningValue.QUATER.value[1])
        self.ui.CamOffsetXSlider.setMaximum(0)
        self.ui.CamOffsetXBox.setMaximum(0)
        self.ui.CamOffsetYSlider.setMaximum(0)
        self.ui.CamOffsetYBox.setMaximum(0)

    def set_ceter_xy(self):
        self.camera.BslCenterX.Execute()
        self.camera.BslCenterY.Execute()

    def update_gain_func(self):
        gain_func = self.ui.CamGainFuncComboBox.currentIndex()
        if gain_func == 0:
            self.camera.GainAuto.Value = "Off"
        elif gain_func == 1:
            self.camera.GainAuto.Value = "Once"
            self.timer.singleShot(1000, self.read_gain)#odczytanie gain i wpisanie do sliders
        else:
            self.camera.GainAuto.Value = "Continuous"

    def update_exp_func(self):
        exp_func = self.ui.CamExpFuncComboBox.currentIndex()
        if exp_func == 0:
            self.camera.ExposureAuto.Value = "Off"
        elif exp_func == 1:
            self.camera.ExposureAuto.Value = "Once"
            self.timer.singleShot(1000, self.read_exp)#odczytanie gain i wpisanie do sliders
        else:
            self.camera.ExposureAuto.Value = "Continuous"

    def chnge_contrast_type(self):
        contrast_type = self.ui.CamContrastTypeComboBox
        if contrast_type == 0:
            self.camera.BslContrastMode.Value = "Linear"
        else:
            self.camera.BslContrastMode.Value = "SCurve"

    def read_gain (self):
        gain = self.camera.Gain.Value
        self.ui.CamGainSlider.setValue(gain)
        self.read_cam_value()

    def read_exp (self):
        exp = self.camera.ExposureTime.Value
        self.ui.CamExpSlider.setValue(exp)
        self.read_cam_value()

    def update_resolution_settings(self, type_change: TypeChange):
        #rozdzielczość pozioma zmiana, co STEP = 4
        if type_change == TypeChange.SLIDER:
            res_x = self.ui.CamWidthSlider.value()
            stepped = round(res_x / STEP) * STEP
            if stepped != res_x:
                res_x = stepped
                self.blockSignals(True)
                self.ui.CamWidthSlider.setValue(res_x)
                self.blockSignals(False)
        else:
            res_x = self.ui.CamWidthBox.value()
            stepped = round(res_x / STEP) * STEP
            if stepped != res_x:
                res_x = stepped
                self.blockSignals(True)
                self.ui.CamWidthBox.setValue(res_x)
                self.blockSignals(False)

        if type_change == TypeChange.SLIDER:
            self.ui.CamWidthBox.setValue(res_x)
        else:
            self.ui.CamWidthSlider.setValue(res_x)

        #wylicznie ofsetu
        res_x_offset = self.ui.CamWidthSlider.maximum() - res_x
        self.ui.CamOffsetXSlider.setMaximum(res_x_offset)
        self.ui.CamOffsetXBox.setMaximum(res_x_offset)

        #rozdzielczość pionowa zmiana
        if type_change == TypeChange.SLIDER:
            res_y = self.ui.CamHighSlider.value()
        else:
            res_y = self.ui.CamHighBox.value()

        if type_change == TypeChange.SLIDER:
            self.ui.CamHighBox.setValue(res_y)
        else:
            self.ui.CamHighSlider.setValue(res_y)

        #wylicznie ofsetu
        res_y_offset = self.ui.CamHighSlider.maximum() - res_y
        self.ui.CamOffsetYSlider.setMaximum(res_y_offset)
        self.ui.CamOffsetYBox.setMaximum(res_y_offset)

    def set_analog_settings(self):
        brightness = self.ui.CamBrightnessSlider.value()
        self.camera.BslBrightness.Value = brightness/10
        contrast = self.ui.CamContrastSlider.value()
        self.camera.BslContrast.Value = contrast/10
        gain = self.ui.CamGainSlider.value()
        self.camera.Gain.Value = gain
        gamma = self.ui.CamGammaSlider.value()
        self.camera.Gamma.Value = gamma/10
        black_level = self.ui.CamBlackLevelSlider.value()
        self.camera.BlackLevel.Value = black_level
        exp_time = self.ui.CamExpSlider.value()
        self.camera.ExposureTime.Value = exp_time
        offset_x = self.ui.CamOffsetXSlider.value()
        self.camera.OffsetX.Value = offset_x
        offset_y = self.ui.CamOffsetYSlider.value()
        self.camera.OffsetY.Value = offset_y
        sharpness_level = self.ui.FiltrSharpnessSlider.value()
        self.camera.BslSharpnessEnhancement.Value = sharpness_level/10
        reduction_level = self.ui.FiltrNoiseSlider.value()
        self.camera.BslNoiseReduction.Value = reduction_level/10

    def update_analog_settings(self, type_change: TypeChange):
        if getattr(self.ui, "loading_settings", False):
                    print("loading_settings =", getattr(self.main_window, "loading_settings", False))
                    return  # Ignorujemy zmiany przy ładowaniu
        #Jasność
        if type_change == TypeChange.SLIDER:
            brightness = self.ui.CamBrightnessSlider.value()
        else:
            brightness = self.ui.CamBrightnessBox.value()

        self.camera.BslBrightness.Value = brightness/10
        if type_change == TypeChange.SLIDER:
            self.ui.CamBrightnessBox.setValue(brightness)
        else:
            self.ui.CamBrightnessSlider.setValue(brightness)


        #Contrast
        if type_change == TypeChange.SLIDER:
            contrast = self.ui.CamContrastSlider.value()
        else:
            contrast = self.ui.CamContrastBox.value()

        self.camera.BslContrast.Value = contrast/10
        if type_change == TypeChange.SLIDER:
            self.ui.CamContrastBox.setValue(contrast)
        else:
            self.ui.CamContrastSlider.setValue(contrast)

        # Wzmocnienie
        if type_change == TypeChange.SLIDER:
            gain = self.ui.CamGainSlider.value()
        else:
            gain = self.ui.CamGainBox.value()

        self.camera.Gain.Value = gain
        if type_change == TypeChange.SLIDER:
            self.ui.CamGainBox.setValue(gain)
        else:
            self.ui.CamGainSlider.setValue(gain)

        #Gamma
        if type_change == TypeChange.SLIDER:
            gamma = self.ui.CamGammaSlider.value()
        else:
            gamma = self.ui.CamGammaBox.value()

        self.camera.Gamma.Value = gamma/10
        if type_change == TypeChange.SLIDER:
            self.ui.CamGammaBox.setValue(gamma)
        else:
            self.ui.CamGammaSlider.setValue(gamma)

        #Poziom czerni
        if type_change == TypeChange.SLIDER:
            black_level = self.ui.CamBlackLevelSlider.value()
        else:
            black_level = self.ui.CamBlackLevelBox.value()

        self.camera.BlackLevel.Value = black_level
        if type_change == TypeChange.SLIDER:
            self.ui.CamBlackLevelBox.setValue(black_level)
        else:
            self.ui.CamBlackLevelSlider.setValue(black_level)

        #Czas ekspozycji
        if type_change == TypeChange.SLIDER:
            exp_time = self.ui.CamExpSlider.value()
        else:
            exp_time = self.ui.CamExpBox.value()

        self.camera.ExposureTime.Value = exp_time
        if type_change == TypeChange.SLIDER:
            self.ui.CamExpBox.setValue(exp_time)
        else:
            self.ui.CamExpSlider.setValue(exp_time)

        #offset poziomo
        if type_change == TypeChange.SLIDER:
            offset_x = self.ui.CamOffsetXSlider.value()
        else:
            offset_x = self.ui.CamOffsetXBox.value()

        self.camera.OffsetX.Value = offset_x
        if type_change == TypeChange.SLIDER:
            self.ui.CamOffsetXBox.setValue(offset_x)
        else:
            self.ui.CamOffsetXSlider.setValue(offset_x)

        #offset w pionie
        if type_change == TypeChange.SLIDER:
            offset_y = self.ui.CamOffsetYSlider.value()
        else:
            offset_y = self.ui.CamOffsetYBox.value()

        self.camera.OffsetY.Value = offset_y
        if type_change == TypeChange.SLIDER:
            self.ui.CamOffsetYBox.setValue(offset_y)
        else:
            self.ui.CamOffsetYSlider.setValue(offset_y)

        #filtr krawędziowy
        if type_change == TypeChange.SLIDER:
            sharpness_level = self.ui.FiltrSharpnessSlider.value()
        else:
            sharpness_level = self.ui.FiltrSharpnessBox.value()

        self.camera.BslSharpnessEnhancement.Value = sharpness_level/10
        if type_change == TypeChange.SLIDER:
            self.ui.FiltrSharpnessBox.setValue(sharpness_level)
        else:
            self.ui.FiltrSharpnessSlider.setValue(sharpness_level)

        #korekcja szumu
        if type_change == TypeChange.SLIDER:
            reduction_level = self.ui.FiltrNoiseSlider.value()
        else:
            reduction_level = self.ui.FiltrNoiseBox.value()

        self.camera.BslNoiseReduction.Value = reduction_level/10
        if type_change == TypeChange.SLIDER:
            self.ui.FiltrNoiseBox.setValue(reduction_level)
        else:
            self.ui.FiltrNoiseSlider.setValue(reduction_level)

        #Odczyt z kamery maksymalnego Fps obliczonego z ograniczeń wewnnętrznych
        self.read_cam_value()

