# This Python file uses the following encoding: utf-8

import cv2
import re
import os
import datetime
import numpy as np
from PySide6 import QtWidgets
from PySide6.QtGui import QPixmap
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QFileDialog
from PySide6.QtCore import Qt
from math import sqrt
import threading
import time
settings_folder_path = "program settings"
filename_settings = "settings.txt"



lines_data = []
#global tempBrightness, tempContrast, tempHue, tempSaturation, tempGamma, tempBalance, tempGain, tempExposure
#tempBrightness = 0
#tempContrast = 0
#tempHue = 0
#tempSaturation = 0
#tempGamma = 0
#tempBalance = 0
#tempGain = 0
#tempExposure = 0
m1 = 0
m2 = 0
b1 = 0
b2 = 0
theta_m1 = 0
theta_m2 = 0
blob_keypoints = 0
merged_rects = 0


class Filters(QtWidgets.QWidget):
    def __init__(self, parent_widget):
        self.ui = parent_widget
        self.capture = None#ponieważ kamera jeszcze nie przypisana
        self.x1 = int(0)
        self.x2 = int(0)
        self.y1 = int(0)
        self.y2 = int(0)
        self.drawing = True
        #wątek analiza obrazu
        self.interwal = 0.015
        self.stop_event = None
        self.event_blob_detection = None
        self.event_display_contours = None
        #sloty podłącznie
        self.slot_connect()
        #wylocznie zakładek przed załączniem kamery
        self.ui.SettingsWidget.setTabEnabled(2, True)
        self.ui.SettingsWidget.setTabEnabled(3, True)
        #odczyt folderu zapisu obrazów
        self.path_save = "~"
        self.path_base_folder = "~"
        #self.path_base_folder = self.read_patch()#jezelibrak utworznie folderu
        #self.folder_create() #wywołanie przy starcie
        #czy folder istnieje z danego dnia o czasie uruchomienia programu
        #self.get_last_time_folder_or_create(path_save)
        # Po pierwszym otrzymaniu obrazu (np. w init):
        self._qimage_buffers = {}



    #obsługa watku               
    def read_event(self, task_func):
        next_time = time.perf_counter()
        while not self.stop_event.is_set():
            actual_time = time.perf_counter()
            if actual_time >= next_time:
                result = self.capture.read() if self.capture else None
                if result is not None:
                    ret, frame = result
                    if ret:
                        task_func(frame)
                next_time += self.interwal
            else:
                time.sleep(max(0, next_time - actual_time))

    def start_threads(self):
        # tworzymy nowe wątki za każdym razem
        self.stop_event = threading.Event()
        self.event_blob_detection = threading.Thread(target=self.read_event, args=(self.blob_detection,), daemon=True)
        self.event_display_contours = threading.Thread(target=self.read_event, args=(self.display_contours,), daemon=True)
        self.event_blob_detection.start()
        self.event_display_contours.start()

    def stop_threads(self):
        if self.stop_event:
            self.stop_event.set()
        if self.event_blob_detection and self.event_blob_detection.is_alive():
            self.event_blob_detection.join()
        if self.event_display_contours and self.event_display_contours.is_alive():
            self.event_display_contours.join()

        # zwalniamy referencje, żeby wątki mogły zostać usunięte
        self.event_blob_detection = None
        self.event_display_contours = None
        self.stop_event = None

    def set_capture(self, capture):
        self.capture = capture

    #pobranie obrazu do analizy
    def update_analize(self):
        ret, frame = self.capture.read()
        if ret:
            self.blob_detection(frame)
            self.display_contours(frame)

#----------------------------------------------------funkcje slotów suwaków i box--------------------------------------
    def slot_connect(self):
        self.ui.PatchPicturesButton.clicked.connect(self.choice_folder_defects)
        self.ui.CountOnCheckBox.clicked.connect(self.take_dimmeter_enabled)
        self.ui.TakeDimButton.clicked.connect(self.take_dimmeter)
        self.ui.AutoDistanceButton.clicked.connect(self.set_lines)

        filtr_tab = self.ui.FiltrTab  # QWidget zakładki

        # zbierz wszystkie slidery, spinboxy i doublespinboxy
        sliders = filtr_tab.findChildren(QtWidgets.QSlider)
        spin_boxes = filtr_tab.findChildren(QtWidgets.QSpinBox)
        double_boxes = filtr_tab.findChildren(QtWidgets.QDoubleSpinBox)

        # dla łatwego wyszukiwania boxów robimy mapę {nazwa: obiekt}
        boxes = {w.objectName(): w for w in (spin_boxes + double_boxes)}

        # przechodzimy tylko po sliderach
        for slider in sliders:
            name = slider.objectName()  # np. "Trs1Slider"
            if not name.endswith("Slider"):
                continue

            box_name = name.replace("Slider", "Box")
            box = boxes.get(box_name)

            if box is None:
                #print(f"⚠ Brak {box_name} dla {name} – pomijam")
                continue

            # funkcje pomocnicze z ochroną przed zapętlaniem
            def slider_to_box(value, box=box):
                box.blockSignals(True)
                box.setValue(value)
                box.blockSignals(False)

            def box_to_slider(value, slider=slider):
                slider.blockSignals(True)
                slider.setValue(value)
                slider.blockSignals(False)

            # podłączenie
            slider.valueChanged.connect(slider_to_box)
            box.valueChanged.connect(box_to_slider)
#----------------------------------------------------wyświetlanie danych w qlabel przez kopiowanie bufora-----------------
    def update_label_with_numpy_image(self, label, frame: np.ndarray, format='BGR', fast = False):
        frame = np.ascontiguousarray(frame)
        height, width, channels = frame.shape
        step = width * channels
        key = id(label)

        if key not in self._qimage_buffers or \
           self._qimage_buffers[key]['width'] != width or \
           self._qimage_buffers[key]['height'] != height:

            qformat = (
                QImage.Format.Format_RGB888 if format.upper() == 'RGB'
                else QImage.Format.Format_BGR888
            )

            qimg = QImage(width, height, qformat)
            ptr = qimg.bits()
            if hasattr(ptr, "setsize"):  # ✅ kompatybilność z PyQt5 i 6
                ptr.setsize(height * step)

            self._qimage_buffers[key] = {
                'qimg': qimg,
                'ptr': ptr,
                'width': width,
                'height': height,
                'step': step
            }

        # 🔹 Nadpisanie danych bez nowej alokacji
        buf = self._qimage_buffers[key]
        np.copyto(
            np.frombuffer(buf['ptr'], dtype=np.uint8).reshape((height, width, channels)),
            frame
        )
        if fast:
            scaled_img = buf['qimg'].scaled(label.width(), label.height(), Qt.IgnoreAspectRatio)
        else:
            scaled_img = buf['qimg'].scaled(
                label.width(),
                label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
        )
        label.setPixmap(QPixmap.fromImage(scaled_img))
#----------------------------------------------------zmiany ustawień--------------------------------------------
    #załącznie przycisku pobrania średniej szerokości
    def take_dimmeter_enabled (self):
        if self.ui.CountOnCheckBox.isChecked():
            self.ui.TakeDimButton.setEnabled(True)
        else:
            self.ui.TakeDimButton.setEnabled(False)

    #funkcja pobierz średnią pomiaru jako referencyjną
    def take_dimmeter (self):
        text_value = self.ui.AvgDimValuelabel.text()
        match = re.search(r"[-+]?\d*\.\d+", text_value)
        try:
            value = float(match.group())
            #value = avg_value_mm
            self.ui.RefDimSpinBox.setValue(value)
        except ValueError:
            print("Nieprawidłowa wartość w AvgDimValuelabel.")
            self.ui.RefDimSpinBox.setValue(1.0)

    #funkcja ustawia linie odniesienia do wyliczonych dla krawędzi
    def set_lines (self):
        global m1, b1, b2
        constant = 50

        #self.ui.DistanceSlider_1.setValue(self.ui.DistanceSlider_1.maximum() - b1 + 5)
        #self.ui.DistanceSlider_2.setValue(b2 - self.ui.DistanceSlider_1.maximum() - 5)

        value = self.ui.DistanceSlider_1.maximum() - b1 + 5 + constant
        if value < 10:
            value = 10
        self.ui.DistanceSlider_1.setValue(value)

        value = b2 - self.ui.DistanceSlider_2.maximum() - 5 + constant
        if value > (self.ui.DistanceSlider_2.maximum() * 2):
            value = (self.ui.DistanceSlider_2.maximum() * 2) - 5
        self.ui.DistanceSlider_2.setValue(value)

        theta_m1 = np.arctan(m1) * (180 / np.pi)
        self.ui.DistanceDegSpinBox.setValue(theta_m1)

    def set_cordinates(self, x1 , y1, x2, y2, drawing):
        self.x1 = x1
        self.x2 = x2
        self.y1 = y1
        self.y2 = y2
        self.drawing = drawing

    def update_settings(self, capture, frame):
        #global tempBrightness, tempContrast, tempHue, tempSaturation, tempGamma, tempBalance, tempGain, tempExposure
        height, width, _ = frame.shape
        # ustawienie slider dla linii referencyjnych
        self.ui.DistanceSlider_1.setMaximum(height/2 - 10)
        self.ui.DistanceSlider_2.setMaximum(height/2 - 5)

    #pobranie obrazu orginalnego
    def update_orginal_frame(self):
        ret, frame = self.capture.read()
        if ret:
            self.update_settings(self.capture, frame)
            self.display_original(frame)

    #wyświetlanie orginalnego obrazu z kamery
    def display_original(self, frame):
        frame_org = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        height, width, channel = frame_org.shape
        label_height = self.ui.label_camera.height()
        label_width = self.ui.label_camera.width()

        # Obliczenie skali dla szerokości i wysokości
        scale_width = width / label_width
        scale_height = height / label_height

        # Przeskalowanie współrzędnych prostokąta
        start_point = (int(self.x1 * scale_width), int(self.y1 * scale_height))
        end_point = (int(self.x2 * scale_width), int(self.y2 * scale_height))
        # draw the rectangle
        cv2.rectangle(frame_org, start_point, end_point, (0, 0, 255), thickness= 2, lineType=cv2.LINE_8)
        frame_org = np.ascontiguousarray(frame_org)
        #height, width, channel = frame_org.shape
        #step = channel * width
        #q_img_org = QImage(frame_org.data, width, height, step, QImage.Format_RGB888)
        #self.ui.label_camera.setPixmap(QPixmap.fromImage(q_img_org).scaled(self.ui.label_camera.width(), self.ui.label_camera.height()))

        self.update_label_with_numpy_image(self.ui.label_camera, frame_org, format='BGR')

#---------------------------------------------------------------------------------------------------------------------------------
    def is_overlapping(self, rect1, rect2, distance=0):
        r1 = np.array(rect1, dtype=float)
        r2 = np.array(rect2, dtype=float)

        r1_end = r1[:2] + r1[2:]
        r2_end = r2[:2] + r2[2:]

        d = float(distance)

        r1_expanded = np.array([r1[0] - d, r1[1] - d, r1_end[0] + d, r1_end[1] + d])
        r2_expanded = np.array([r2[0] - d, r2[1] - d, r2_end[0] + d, r2_end[1] + d])

        no_overlap = (
            (r1_expanded[2] < r2_expanded[0]) |
            (r2_expanded[2] < r1_expanded[0]) |
            (r1_expanded[3] < r2_expanded[1]) |
            (r2_expanded[3] < r1_expanded[1])
        )

        return not no_overlap


    def merge_two_rectangles(self, rect1, rect2):
        r1 = np.array(rect1, dtype=float)
        r2 = np.array(rect2, dtype=float)

        xy_min = np.minimum(r1[:2], r2[:2])
        xy_max = np.maximum(r1[:2] + r1[2:], r2[:2] + r2[2:])
        wh = xy_max - xy_min

        return tuple(np.concatenate((xy_min, wh)))


    def merge_overlapping_blobs(self, rects, distance=0):
        """
        Łączy wszystkie prostokąty lub KeyPointy z listy, które nachodzą na siebie
        lub są w odległości <= distance.
        Zwraca listę krotek (x, y, w, h).
        """
        #Jeśli wejście to lista KeyPointów — konwertujemy na prostokąty
        if len(rects) > 0 and isinstance(rects[0], cv2.KeyPoint):
            rects = [(kp.pt[0] - kp.size / 2,
                      kp.pt[1] - kp.size / 2,
                      kp.size,
                      kp.size) for kp in rects]

        rects = np.array(rects, dtype=float)
        merged = True

        while merged:
            merged = False
            new_rects = []
            used = np.zeros(len(rects), dtype=bool)

            for i in range(len(rects)):
                if used[i]:
                    continue
                rect = rects[i]
                overlapping = []

                for j in range(i + 1, len(rects)):
                    if used[j]:
                        continue
                    if self.is_overlapping(rect, rects[j], distance=distance):
                        overlapping.append(j)

                if overlapping:
                    group = np.vstack([rects[[i] + overlapping]])
                    xy_min = np.min(group[:, :2], axis=0)
                    xy_max = np.max(group[:, :2] + group[:, 2:], axis=0)
                    merged_rect = np.concatenate((xy_min, xy_max - xy_min))
                    new_rects.append(merged_rect)
                    used[i] = True
                    used[overlapping] = True
                    merged = True
                else:
                    new_rects.append(rect)

            rects = np.array(new_rects)

        return [tuple(r) for r in rects]


    #def blob_detection (self, frame):#self.queue, self.frame
    def blob_detection (self, frame):
        global blob_keypoints
        global merged_rects
        result = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        #przygotowanie obrazu dla detekcji zniekształceń na krawędziach obrazu(zmkniecie obrysu)
        #dodanie czarnych linii po obu stronch
        height, width = result.shape#pobranie wymiarów obrazu
        for y_coords in range(height):
            cv2.circle(result, (0, y_coords), 1, (0, 0, 0), -1)
            cv2.circle(result, (width, y_coords), 1, (0, 0, 0), -1)


        if self.ui.MonoCheckBox.isChecked():
            t1 = max(0, self.ui.Trs1LNSlider.value())
            t2 = max(t1 + 10, self.ui.Trs2LNSlider.value())
            _, result = cv2.threshold(result, t1, t2, cv2.THRESH_BINARY)#zamiana na obraz binarny - progowanie
        #odwrócenie kolorów, detekcja białych plam na ciemnym tle
        result = cv2.bitwise_not(result)

        # Setup SimpleBlobDetector parameters.
        params = cv2.SimpleBlobDetector_Params()

        # Change thresholds
        params.minThreshold = self.ui.TrsMinSlider.value()
        params.maxThreshold = self.ui.TrsMaxSlider.value()

        # Filter by Area.
        params.filterByArea = True
        params.minArea = self.ui.AreaMinSlider.value()
        params.maxArea = self.ui.AreaMaxSlider.value()

        # Filter by Circularity
        params.filterByCircularity = True
        params.minCircularity = self.ui.CircMinSlider.value()/10
        #params.maxCircularity = self.ui.CircMaxSlider.value()/10

        # Filter by Convexity
        params.filterByConvexity = True
        params.minConvexity = self.ui.ConvMinSlider.value()/10
        #params.maxConvexity = self.ui.ConvMaxSlider.value()/10

        # Filter by Inertia
        params.filterByInertia = True
        params.minInertiaRatio = self.ui.InertiaMinSlider.value()/100
        #params.maxInertiaRatio = self.ui.InertiaMaxSlider.value()/100

        # Create a detector with the parameters
        ver = (cv2.__version__).split('.')
        if int(ver[0]) < 3 :
         detector = cv2.SimpleBlobDetector(params)
        else :
         detector = cv2.SimpleBlobDetector_create(params)
        #wywołanie dwtekcji
        blob_keypoints = detector.detect(result)
        #łączenie blobów nachodzacych na siebie
        pixels_sum_rects = self.ui.pxSumBox.value()
        merged_rects = self.merge_overlapping_blobs(blob_keypoints, pixels_sum_rects)


        if self.ui.DispalyBlobCheckBox.isChecked():
            #for (x, y, w, h) in merged_rects:
                 #cv2.rectangle(result, (x, y), (x+w, y+h), (0, 255, 0), 2)

            #rysowanie w obrazie
            im_with_keypoints = cv2.drawKeypoints(result, blob_keypoints, np.array([]), (0,0,255), cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
            # #step = result.shape[1]
            #height, width = result.shape
            #q_img_filtr = QImage(im_with_keypoints.data, width, height, width * im_with_keypoints.shape[2], QImage.Format_RGB888)
            #self.ui.label_image_analize.setPixmap(QPixmap.fromImage(q_img_filtr).scaled(self.ui.label_image_analize.width() - (self.ui.label_image_analize.frameWidth() * 2) , self.ui.label_image_analize.height()))
            self.update_label_with_numpy_image(self.ui.label_image_analize, im_with_keypoints, format='RGB')
            print(f"Liczba wykrytych obiektów: {len(blob_keypoints)}")
        #queue.put(wynik)

#filtracja błędu nec lump na podtawie ilości punktów rozmieszczonych przy sobie(odleglość jako promiń)
    def check_points_distance(self, lump_nec_points_x, lump_nec_points_y):
        min_length = int(self.ui.LenghtValueSpinBox.value() * self.ui.pxmmBox.value())
        radius = min_length

        # Zamiana list na tablice numpy
        x = np.asarray(lump_nec_points_x)
        y = np.asarray(lump_nec_points_y)

        # Oblicz macierz odległości (bez pętli)
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        distances = np.sqrt(dx**2 + dy**2)

        # Dla każdego punktu referencyjnego sprawdzamy, które punkty są w promieniu
        in_radius = distances <= radius

        # Teraz sprawdzamy czy dla któregokolwiek punktu istnieje ciąg >= min_length punktów w promieniu
        # Uwaga: interpretacja "po kolei po sobie" zależy od Twojej intencji – tu zakładam kolejność po indeksie
        for i in range(len(x)):
            # wektor bool dla punktu referencyjnego i
            mask = in_radius[i]
            # zamień True/False na 1/0
            arr = mask.astype(int)
            # sprawdź czy jest podciąg długości min_length z samymi 1
            if np.any(np.convolve(arr, np.ones(min_length, dtype=int), mode='valid') == min_length):
                return True

        return False
#filtracja błędu nec lump na podtawie ilości punktów rozmieszczonych przy sobie po x, pounkty leżą pokolei po sobie

    def check_points_distance_x(self, lump_nec_points_x):
        min_length = int(self.ui.LenghtValueSpinBox.value() * self.ui.pxmmBox.value())

        # Zamiana listy na tablicę numpy
        x = np.asarray(lump_nec_points_x)

        # Obliczamy macierz odległości w osi X (różnice bezwzględne)
        dist = np.abs(x[:, None] - x[None, :])

        # Maska logiczna: True jeśli punkty są w odległości <= min_length
        in_range = dist <= min_length

        # Szukamy sekwencji co najmniej min_length kolejnych punktów (po indeksach)
        for i in range(len(x)):
            mask = in_range[i]
            arr = mask.astype(int)
            if np.any(np.convolve(arr, np.ones(min_length, dtype=int), mode='valid') == min_length):
                return True

        return False

#wyznacznie konturów
    def display_contours(self, frame):
        global m1, b1, m2, b2, theta_m1, theta_m2
        # Konwersja na obraz w odcieniach szarości
        result = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        orginal_image = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
        result_filter = result

        if self.ui.AproxBox.isChecked() :
            #progowanie krawędziowe lub binarne
            t1 = max(0, self.ui.Trs1Slider.value())
            t2 = max(t1 + 1, self.ui.Trs2Slider.value())
            index_trs = self.ui.TrsNrBox.currentIndex()
            # Mapowanie indeksów na odpowiednie typy progowania
            threshold_types = [
                cv2.THRESH_BINARY,
                cv2.THRESH_BINARY_INV,
                cv2.THRESH_TOZERO,
                cv2.THRESH_TOZERO_INV
            ]
            # Wybór typu progowania (domyślnie THRESH_BINARY w przypadku indeksu poza zakresem)
            threshold_type = threshold_types[index_trs] if 0 <= index_trs < len(threshold_types) else cv2.THRESH_BINARY
            _, result = cv2.threshold(result_filter, t1, t2, threshold_type)#zamiana na obraz binarny - progowanie

            # Wymiary obrazu
            height, width = result.shape

            # --- Wersja NUMPY: wyszukiwanie pierwszego czarnego piksela w każdej kolumnie ---
            # maska pikseli czarnych (0)
            mask = (result == 0)

            # od góry — pierwsze wystąpienie czarnego piksela
            y_top = np.argmax(mask, axis=0)  # pierwsze True w każdej kolumnie
            valid_top = mask[y_top, np.arange(width)]  # sprawdzenie, gdzie faktycznie istnieje czarny piksel
            edge_points_x1 = np.arange(width)[valid_top]
            edge_points_y1 = y_top[valid_top]

            # od dołu — odwrócony obraz
            mask_flipped = np.flipud(mask)
            y_bottom_from_end = np.argmax(mask_flipped, axis=0)
            valid_bottom = mask_flipped[y_bottom_from_end, np.arange(width)]
            edge_points_x2 = np.arange(width)[valid_bottom]
            edge_points_y2 = height - 1 - y_bottom_from_end[valid_bottom]

            # --- Dopasowanie prostych ---
            if len(edge_points_x1) > 1 and len(edge_points_x2) > 1:
                m1, b1 = np.polyfit(edge_points_x1, edge_points_y1, 1)
                m2, b2 = np.polyfit(edge_points_x2, edge_points_y2, 1)

                result_image = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
                x_coords = np.arange(width)

                # Linia górna
                y_coords1 = (m1 * x_coords + b1).astype(int)
                mask1 = (y_coords1 >= 0) & (y_coords1 < height)
                pts1 = np.column_stack((x_coords[mask1], y_coords1[mask1]))
                cv2.polylines(result_image, [pts1.reshape(-1, 1, 2)], False, (255, 0, 0), 2)
                if self.ui.EdgeOnCheckBox.isChecked():
                    cv2.polylines(orginal_image, [pts1.reshape(-1, 1, 2)], False, (255, 0, 0), 2)

                # Środek linii górnej
                center_x1 = (x_coords[0] + x_coords[-1]) / 2
                center_y1 = (y_coords1[0] + y_coords1[-1]) / 2

                # Linia dolna
                y_coords2 = (m2 * x_coords + b2).astype(int)
                mask2 = (y_coords2 >= 0) & (y_coords2 < height)
                pts2 = np.column_stack((x_coords[mask2], y_coords2[mask2]))
                cv2.polylines(result_image, [pts2.reshape(-1, 1, 2)], False, (255, 0, 0), 2)
                if self.ui.EdgeOnCheckBox.isChecked():
                    cv2.polylines(orginal_image, [pts2.reshape(-1, 1, 2)], False, (255, 0, 0), 2)

                # Środek linii dolnej
                center_x2 = (x_coords[0] + x_coords[-1]) / 2
                center_y2 = (y_coords2[0] + y_coords2[-1]) / 2

                y_coords = (m2 * x_coords + b2).astype(int)
                for i in range(len(x_coords) - 1):
                    if 0 <= y_coords[i] < height and 0 <= y_coords[i + 1] < height:
                        cv2.line(result_image, (x_coords[i], y_coords[i]), (x_coords[i + 1], y_coords[i + 1]), (255, 0, 0), 2)#dolna linia czerwona
                        if self.ui.EdgeOnCheckBox.isChecked():#wloncznie widoczności linii na obrazie
                            cv2.line(orginal_image, (x_coords[i], y_coords[i]), (x_coords[i + 1], y_coords[i + 1]), (255, 0, 0), 2)
                        #cv2.line(result_image, (x_coords[i], y_coords[i]+shift_distance), (x_coords[i + 1], y_coords[i + 1]+shift_distance), (0, 255, 0), 2)
                #oblicznie srodka linii x,y
                dx2 = (x_coords[0] + x_coords[len(x_coords) - 1])
                center_x2 = dx2 / 2# Obliczenie środka linii wsp x
                dy2 = (y_coords[0] + y_coords[len(y_coords) - 1])
                center_y2 = dy2 / 2# Obliczenie środka linii wsp y

                distance_px = sqrt((center_x2 - center_x1)**2 + (center_y2 - center_y1)**2)
                distance_mm = distance_px / self.ui.pxmmBox.value()
                self.ui.mmlabel.setText(f"Odległość: {distance_mm:.2f} mm")

                # Wyświetlenie obrazu
                if self.ui.DispalyConCheckBox.isChecked():
                    #height, width, _ = result_image.shape
                    #step = result_image.shape[1] * result_image.shape[2]
                    #q_img_filtr = QImage(result_image.data, width, height, step, QImage.Format_RGB888)
                    #self.ui.label_image_analize.setPixmap(QPixmap.fromImage(q_img_filtr).scaled(self.ui.label_image_analize.width(), self.ui.label_image_analize.height()))
                    self.update_label_with_numpy_image(self.ui.label_image_analize, result_image, format='RGB')
                #sprawdzenie czy obraz do analizy jest ustawiony prawidłowo
                #oblicznie kąta
                theta_m1 = np.arctan(m1) * (180 / np.pi)
                self.ui.DistanceDegLine1Edit.setText(f"{theta_m1:.1f}")
                theta_m2 = np.arctan(m2) * (180 / np.pi)
                self.ui.DistanceDegLine2Edit.setText(f"{theta_m2:.1f}")
                abs_theta_m2_m1 = abs(theta_m2 - theta_m1)
                self.ui.DiffDegLineEdit.setText(f"{abs_theta_m2_m1:.1f}")
                abs_theta_m1 = abs(theta_m1)
                abs_theta_m2 = abs(theta_m2)
                #sprawdznie kata pochylenia obrazu
                theta_ok = False
                if((abs_theta_m1 < 1.5) and (abs_theta_m2 < 1.5)):
                    theta_ok = True
                position_ok = False
                # sprawdzanie umiejscowienia obrazu
                if (edge_points_y1[0] > 10 and edge_points_y1[0] < (height/2 -10) and edge_points_y1[len(edge_points_y1)-1] > 10 and edge_points_y1[len(edge_points_y1) - 1] < (height/2-10)
                    and edge_points_y2[0] < (height-10) and edge_points_y2[0] > (height/2 + 10) and edge_points_y2[len(edge_points_y2)-1] < (height-10) and edge_points_y2[len(edge_points_y2)-1] > (height/2 + 10)):
                    position_ok = True
                position_ok = True
                # mozliwość załącznia przelicznaia
                if theta_ok and position_ok:
                    self.ui.CountOnCheckBox.setEnabled(True)
                else:
                    self.ui.CountOnCheckBox.setEnabled(False)

                #sprawdzenie ustawienia w góra dół
            else:
                print("Za mało punktów do dopasowania prostej")


#analiza pomiędzy ustalonymi liniami szerokości po prostej prostopadłej
            fault_nec = False
            fault_lump = False
            #analiza lump/nec
            distance_b1 = self.ui.DistanceSlider_1.value()
            distance_b2 = self.ui.DistanceSlider_2.value()
            distance_m1 = np.tan(np.deg2rad(self.ui.DistanceDegSpinBox.value()))
            t1NecLump = max(0, self.ui.Trs1NecLumpSlider.value())
            _, result = cv2.threshold(result_filter, t1NecLump, t2, cv2.THRESH_BINARY)
            # Wyświetlenie obrazu
            if self.ui.DispalyNecLumpCheckBox.isChecked():
                #result_image = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)  # Konwersja na obraz kolorowy
                height, width, _ = result_image.shape
                #step = result_image.shape[1] * result_image.shape[2]
                #q_img_filtr = QImage(result_image.data, width, height, step, QImage.Format_RGB888)
                #self.ui.label_image_analize.setPixmap(QPixmap.fromImage(q_img_filtr).scaled(self.ui.label_image_analize.width(), self.ui.label_image_analize.height()))
                self.update_label_with_numpy_image(
                    self.ui.label_image_analize,
                    result_image,
                    format='BGR'
                )

            height, width = result.shape
            x_coords = np.arange(width)
            y_coords = np.arange(height)
            y_coords_line1 = (distance_m1 * x_coords + (height/2 - distance_b1)).astype(int)
            y_coords_line2 = (distance_m1 * x_coords + (height/2 + distance_b2)).astype(int)

            #numpy
            if self.ui.CountOnCheckBox.isChecked():
                # Przygotowanie współrzędnych
                y1 = np.clip(y_coords_line1, 0, height - 1)
                y2 = np.clip(y_coords_line2, 0, height - 1)
                xs = np.arange(width)

                # Maska zakresu między liniami
                Y = np.arange(height)[:, None]  # shape: (height, 1)
                region_mask = (Y >= y1) & (Y <= y2)
                black_mask = (result == 0) & region_mask

                # --- pierwszy czarny piksel od góry ---
                has_black_top = black_mask.any(axis=0)
                y_top = np.where(has_black_top, black_mask.argmax(axis=0), height // 2)

                # --- pierwszy czarny piksel od dołu ---
                black_mask_flipped = black_mask[::-1, :]
                has_black_bottom = black_mask_flipped.any(axis=0)
                y_bottom = np.where(has_black_bottom, height - black_mask_flipped.argmax(axis=0) - 1, height // 2)

                # --- wyrównanie długości tablic (jeśli coś poszło nie tak) ---
                # w praktyce przy tym podejściu długości zawsze są równe,
                # ale dla bezpieczeństwa można dodać:
                min_len = min(len(y_top), len(y_bottom))
                y_top = y_top[:min_len]
                y_bottom = y_bottom[:min_len]
                xs = xs[:min_len]

                # --- obliczenie różnic pionowych ---
                delta_points_y = y_bottom - y_top  # różnica między krawędziami

                # --- końcowe tablice wyników ---
                edge_points_x1 = xs
                edge_points_y1 = y_top
                edge_points_x2 = xs
                edge_points_y2 = y_bottom

            #znalezienie największej odchyłki w górę i dół, porównanie do wymiaru nominalnego
                max_value = max(delta_points_y)#maksymalna szerokość
                min_value = min(delta_points_y)#minimalna szerokość
                avg_value = 0
                #for i in range(len(delta_points_y)):
                #    avg_value += delta_points_y[i]
                #avg_value /= len(delta_points_y)
                avg_value = sum(delta_points_y) / len(delta_points_y)
                avg_value_mm = avg_value / self.ui.pxmmBox.value()
                max_value_mm = max_value / self.ui.pxmmBox.value()
                min_value_mm = min_value / self.ui.pxmmBox.value()
            #wyświetlenie wartości min/max/średnia
                self.ui.MaxDimValuelabel.setText(f"Max:{max_value_mm:.2f}mm")
                self.ui.MinDimValuelabel.setText(f"Min:{min_value_mm:.2f}mm")
                self.ui.AvgDimValuelabel.setText(f"Avg:{avg_value_mm:.2f}mm")
                #self.ui.AvgDimValuelabel.setText(f"{avg_value_mm:.2f}")
            #lump
                text_distance_mm = self.ui.RefDimSpinBox.value()
                ref_distance_mm = float(text_distance_mm)
                text_lump_val_mm = self.ui.LumpValueSpinBox.value()
                lump_val_mm = float(text_lump_val_mm)
                lump_distance_mm = ref_distance_mm + lump_val_mm
                if max_value_mm > lump_distance_mm:
                    self.ui.LumpValuelabel.setText(f"Lump:{max_value_mm:.2f}mm")
                    fault_lump = True
                else:
                    self.ui.LumpValuelabel.setText("Lump:----mm")
                    fault_lump = False
            #nec
                text_nec_val_mm = self.ui.NecValueSpinBox.value()
                nec_val_mm = float(text_nec_val_mm)
                nec_distance_mm = ref_distance_mm - nec_val_mm
                if min_value_mm < nec_distance_mm:
                    self.ui.NecValuelabel.setText(f"Nec:{min_value_mm:.2f}mm")
                    fault_nec = True
                else:
                    self.ui.NecValuelabel.setText("Nec:----mm")
                    fault_nec = False
                #zaznacznie wartości przekraczajacych ochyłkę
                    #tablice wartości wsp. lump/nec dla filtru odległości po okregu
                #numpy
                # Załóżmy, że edge_points_y1 i edge_points_y2 to tablice NumPy
                edge_points_y1 = np.asarray(edge_points_y1)
                edge_points_y2 = np.asarray(edge_points_y2)

                # obliczamy różnicę w milimetrach dla wszystkich pikseli naraz
                delta_mm = (edge_points_y2 - edge_points_y1) / self.ui.pxmmBox.value()

                # maski logiczne
                mask_lump = delta_mm > lump_distance_mm
                mask_nec = delta_mm < nec_distance_mm

                # współrzędne pikseli spełniających warunki
                x_vals = np.arange(width)

                lump_x = x_vals[mask_lump]
                lump_y1 = edge_points_y1[mask_lump]
                lump_y2 = edge_points_y2[mask_lump]

                nec_x = x_vals[mask_nec]
                nec_y1 = edge_points_y1[mask_nec]
                nec_y2 = edge_points_y2[mask_nec]

                # opcjonalnie: połącz dane w jedną strukturę (tak jak w oryginale)
                lump_nec_points_x = np.concatenate([lump_x, nec_x])
                #lump_nec_points_y1 = np.concatenate([lump_y1, nec_y1])
                #lump_nec_points_y2 = np.concatenate([lump_y2, nec_y2])

                # rysowanie punktów (jeśli trzeba każdy osobno)
                for (x, y1, y2) in zip(lump_x, lump_y1, lump_y2):
                    cv2.circle(orginal_image, (int(x), int(y1)), 2, (0, 0, 255), -1)
                    cv2.circle(orginal_image, (int(x), int(y2)), 2, (0, 0, 255), -1)

                for (x, y1, y2) in zip(nec_x, nec_y1, nec_y2):
                    cv2.circle(orginal_image, (int(x), int(y1)), 2, (0, 0, 100), -1)
                    cv2.circle(orginal_image, (int(x), int(y2)), 2, (0, 0, 100), -1)
                #filtr błędu dł. okregu - określenie ilości pikseli sąsiadujących przekraczajacych wartość(dł. lump/nec)
                    #check_min_lenght = self.check_points_distance(lump_nec_points_x, lump_nec_points_y1)
                #filtr ilość pikseli lump/nec po wsp. x
                if self.ui.LenghtCheckBox.isChecked():
                    check_min_lenght = self.check_points_distance_x(lump_nec_points_x)
                else:
                    check_min_lenght = True
            #wyświetlenie linii na obrazie
            for i in range(len(x_coords) - 1):
                if 0 <= y_coords_line1[i] < height and 0 <= y_coords_line1[i + 1] < height:
                    cv2.line(orginal_image, (x_coords[i], y_coords_line1[i]), (x_coords[i + 1], y_coords_line1[i + 1]), (0, 255, 0), 1)
            for i in range(len(x_coords) - 1):
                if 0 <= y_coords_line2[i] < height and 0 <= y_coords_line2[i + 1] < height:
                    cv2.line(orginal_image, (x_coords[i], y_coords_line2[i]), (x_coords[i + 1], y_coords_line2[i + 1]), (0, 255, 0), 1)
            #oblicznie rozmiaru i zakresu kolorów
            height, width, channel = orginal_image.shape
            #step = channel * width
            #wyświetlenie obrazu lump/nec
            #q_img_filtr = QImage(orginal_image.data, width, height, step, QImage.Format_RGB888)
            #dodanie obrazu zniekształceń
            #rysuje prostokąt ograniczjacy bloby
            #for (x, y, w, h) in merged_rects:
                 #cv2.rectangle(orginal_image, (x, y), (x+w, y+h), (0, 0, 255), 2)
            for (x, y, w, h) in merged_rects:
                x, y, w, h = map(int, [x, y, w, h])
                cv2.rectangle(orginal_image, (x, y), (x + w, y + h), (0, 0, 255), 2)
            #rysuje bloby
            #im_with_keypoints = cv2.drawKeypoints(orginal_image, blob_keypoints, np.array([]), (0,0,255), cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
            #blob_image = QImage(im_with_keypoints.data, width, height, width * im_with_keypoints.shape[2], QImage.Format_RGB888)
            #wyświetlenie w oknie bloby i prostokąt ograniczjący
            #self.ui.label_image.setPixmap(QPixmap.fromImage(blob_image).scaled(self.ui.label_image.width(), self.ui.label_image.height()))
            #rysuje sam prostokąt ograniczjacy bloby
            #height, width, channel = orginal_image.shape
            #step = channel * width
            #q_img_out = QImage(orginal_image.data, width, height, step, QImage.Format_RGB888)
            #self.ui.label_image.setPixmap(QPixmap.fromImage(q_img_out).scaled(self.ui.label_image.width(), self.ui.label_image.height()))
            self.update_label_with_numpy_image(
                self.ui.label_image,
                orginal_image,
                format='RGB'
            )
            #
            #zapis do pliku
            if (((fault_nec or fault_lump) and check_min_lenght) or len(blob_keypoints) > 0) and self.ui.SavePictureCheckBox.isChecked():
                print("Wywołanie zapisu")
                #ścieżka
                #path = "C:/Users/ur/Pictures/lump_nec"

                #self.save_image(self.ui.label_image.pixmap(), path)
                #dodanie opisu
                text_down = self.ui.MaxDimValuelabel.text() + " " + self.ui.MinDimValuelabel.text() + " " + self.ui.AvgDimValuelabel.text() \
                + " " + self.ui.LumpValuelabel.text() + " " + self.ui.NecValuelabel.text()

                #text_image = self.add_text_to_image(orginal_image, text_up, text_down)

                if self.ui.PlcUseCheckBox.isChecked() and (self.ui.AnalizeSpeedBox.value() < int(float(self.ui.SpeedEdit.text()))):
                    text_up =  "Tol. Lump:" + self.ui.LumpValueSpinBox.text() + "mm" + " " + "Tol. Nec:" + self.ui.NecValueSpinBox.text() + "mm" \
                    + " " + "Licznik:" + self.ui.CountEdit.text() + "m" + " " + "Predkosc:" + self.ui.SpeedEdit.text() + "m/min"

                    #text_image = self.add_text_to_image(im_with_keypoints, text_up, text_down)
                    text_image = self.add_text_to_image(orginal_image, text_up, text_down)
                    #zapis
                    self.save_image_CV(text_image, self.path_save)
                elif not self.ui.PlcUseCheckBox.isChecked():
                    text_up =  "Tol. Lump:" + self.ui.LumpValueSpinBox.text() + "mm" + " " + "Tol. Nec:" + self.ui.NecValueSpinBox.text() + "mm" + " " + "Licznik:-----m"
                    #text_image = self.add_text_to_image(im_with_keypoints, text_up, text_down)
                    text_image = self.add_text_to_image(orginal_image, text_up, text_down)
                    self.save_image_CV(text_image, self.path_save)
#---------------------------------------------------------------- operacje na plikach -------------------------------------------------------
    #zapis z uzyciem opencv szybszy
    def save_image_CV(self, image, folder_path: str):
        #sprawdza czy folder z datą dnia istnieje przy starcie zapisu
        #full_path_save = self.get_last_time_folder_or_create(folder_path)
        full_path_save = folder_path

        now = datetime.datetime.now()#pobranie czasu systemowego
        #date_str = now.strftime("%Y_%m_%d")#data rok_miesiac_dzień
        #full_path_save = os.path.join(folder_path, date_str)#full_path_save = path_save + date_str
        #if not os.path.exists(full_path_save):#jeżeli folder nie istnieje to go tworzy
            #os.makedirs(full_path_save)

        #if not os.path.exists(folder_path):#jeżeli folder nie istnieje to go tworzy
            #os.makedirs(folder_path)

        #now = datetime.datetime.now()#pobranie czasu systemowego
        #ms = now.strftime("%f")[:3]
        #filename = now.strftime("%H_%M_%S") + "_" + ms + ".png"
        #filename = datetime.datetime.now().strftime("%H_%M_%S_%f")[:-3]
        #filename = datetime.datetime.now().strftime("Data%Y-%m-%d_Godzina%H_%M_%S_%f")[:-3]
        filename = now.strftime("%H_%M_%S_%f")[:-3]
        file_path = os.path.join(full_path_save, f"{filename}.png") #dodanie do ścieżki nazwy pliku

        ret = cv2.imwrite(file_path, image)#zapis za pomoca open cv
        #zapis
        if ret:
            print(f"Obraz zapisany jako {file_path}")
        else:
            print("Nie udało się zapisać obrazu.")

    #zapis z użyciem mapy QPixmap
    def save_image(self, pixmap: QPixmap, folder_path: str):
        now = datetime.datetime.now()#pobranie czasu systemowego
        ms = now.strftime("%f")[:3]
        filename = now.strftime("%H_%M_%S") + "_" + ms + ".png"
        #filename = now.strftime("%H_%M_%S") + ".png"  #generowanie nazwy npliku
        full_path = os.path.join(folder_path, filename)#dodanie do ścieżki nazwy pliku

        if not os.path.exists(folder_path):#jeżeli folder nie istnieje to go tworzy
            os.makedirs(folder_path)

        #zapis
        if pixmap.save(full_path, "PNG"):
            print(f"Obraz zapisany jako {full_path}")
        else:
            print("Nie udało się zapisać obrazu.")


    def add_text_to_image(self, image, text_up, text_down):
        """ Dodaje tekst do obrazu w prawym dolnym rogu """
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        color = (0, 0, 200)  #kolor tekstu
        thickness = 1

        # Obliczenie rozmiaru tekstu
        text_size = cv2.getTextSize(text_up, font, font_scale, thickness)[0]
        # Obliczenie pozycji tekstu góura #height, width, channel = orginal_image.shape
        #text_x = text_size[0] - 10  # 10px margines od prawej krawędzi
        text_x = 10
        text_y = 10 + text_size[1]   # 10px margines od dolnej krawędzi
        # Dodanie tekstu do obrazu
        #cv2.putText(image, text_up, (text_x, text_y), font, font_scale, color, thickness, cv2.LINE_AA)
        cv2.putText(image, text_up, (text_x, text_y), font, font_scale, color, thickness, cv2.LINE_AA)

        # Obliczenie rozmiaru tekstu
        text_size = cv2.getTextSize(text_down, font, font_scale, thickness)[0]
        # Obliczenie pozycji tekstu (prawy dolny róg)
        #text_x = image.shape[1] - text_size[0] - 10  # 10px margines od prawej krawędzi
        text_x = 10
        text_y = image.shape[0] - 10  # 10px margines od dolnej krawędzi
        # Dodanie tekstu do obrazu
        cv2.putText(image, text_down, (text_x, text_y), font, font_scale, color, thickness, cv2.LINE_AA)

        return image
#---------------------------------------------------- operacje na folderach ----------------------------------------------------
    #wybór folderu do zapisu obrazów z defektami
    def read_patch(self):
        file_path_settings = os.path.join(settings_folder_path, filename_settings)

        # Domyślny folder, jeśli plik nie istnieje lub brak trzeciej linii
        default_folder = "~"

        # Próba odczytania trzeciej linii z pliku
        third_line = default_folder
        if os.path.exists(file_path_settings):
            try:
                with open(file_path_settings, "r", encoding="utf-8") as f:
                    for i, line in enumerate(f, start=1):
                        if i == 3:
                            third_line = line.strip()
                            print("Folder zdjęć:", third_line)
                            break
            except Exception as e:
                print("Błąd podczas odczytu pliku:", e)

        else:
            print("Plik nie istnieje:", file_path_settings)
        return third_line

    def choice_folder_defects(self):
        third_line_patch = self.read_patch()#odczyt patch dla folderu ustawień

        # Wyświetlenie okna dialogowego do wyboru folderu
        folder_path = QFileDialog.getExistingDirectory(
            None,
            "Wybierz folder do zapisu",
            os.path.expanduser(third_line_patch),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if not folder_path:#czy folder wybrany
                print("Użytkownik anulował wybór folderu")
                return  # użytkownik nie wybrał folderu
        print("Wybrany folder:", folder_path)

        # Wczytanie wszystkich linii istniejącego pliku ustawień
        lines = []
        file_path_settings = os.path.join(settings_folder_path, filename_settings)
        if os.path.exists(file_path_settings):
            with open(file_path_settings, "r", encoding="utf-8") as f:
                lines = f.readlines()#odczyt wszystkich linii
        # Upewnienie się, że plik ma przynajmniej 3 linie
        while len(lines) < 3:#czy mniej niż trzy wiersze
            lines.append("\n")#zwiększenie o wiersz
            # Zapis folderu w trzeciej linii
        lines[2] = folder_path + "\n" #dopisanie patch
        # Nadpisanie pliku ustawień
        with open(file_path_settings, "w", encoding="utf-8") as f:
            f.writelines(lines)

    #pobiera nazwę ostniego utworzonego folderu(lub go tworzy o nazwie czasu utworzenia) w folderze głównym o dacie bieżącej(lub go tworzy)
    def get_last_time_folder_or_create(self, base_folder):
        # pobierz aktualną datę
        now = datetime.datetime.now()
        date_str = now.strftime("%Y_%m_%d")

        # główny folder daty
        date_folder = os.path.join(base_folder, date_str)

        # utwórz folder daty jeśli nie istnieje
        os.makedirs(date_folder, exist_ok=True)

        # pobierz listę podfolderów
        subfolders = [f for f in os.listdir(date_folder) if os.path.isdir(os.path.join(date_folder, f))]

        # sortowanie folderów po nazwie (czasie)
        subfolders_sorted = sorted(subfolders)

        # jeśli istnieją, to ostatni folder czasu
        last_time_folder = subfolders_sorted[-1] if subfolders_sorted else None

        # jeżeli brak podfolderów → tworzymy pierwszy
        if last_time_folder is None:
            time_str = now.strftime("%H_%M_%S")
            last_time_folder = time_str
            os.makedirs(os.path.join(date_folder, last_time_folder))
            return os.path.join(date_folder, last_time_folder)

        # jeżeli istnieją foldery → zwróć ostatni
        return os.path.join(date_folder, last_time_folder)

    #tworzy nowy podfolder z nazwą o czasie utworzenia jezeli ten sam czas dodaje kolejny numer
    def create_new_time_folder(self, base_folder):
        # aktualna data
        now = datetime.datetime.now()
        date_str = now.strftime("%Y_%m_%d")

        # ścieżka do folderu daty
        date_folder = os.path.join(base_folder, date_str)
        os.makedirs(date_folder, exist_ok=True)

        # baza nazwy folderu czasu
        time_str = now.strftime("%H_%M_%S")
        new_folder_name = time_str
        new_folder_path = os.path.join(date_folder, new_folder_name)

        # zabezpieczenie jeśli folder w tej samej sekundzie już istnieje
        counter = 1
        while os.path.exists(new_folder_path):
            new_folder_name = f"{time_str}_{counter}"
            new_folder_path = os.path.join(date_folder, new_folder_name)
            counter += 1

        os.makedirs(new_folder_path)  # tworzymy folder
        return new_folder_path

    #tworznie folderu po starcie zapisu lub resecie licznika
    def folder_create(self):
        self.path_base_folder = self.read_patch()#jezelibrak utworznie folderu z datą bierzacą
        self.path_save = self.create_new_time_folder(self.path_base_folder)























