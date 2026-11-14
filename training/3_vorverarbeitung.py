"""
Vorverarbeitung von Beleg- und Rechnungsbildern.

Pipeline pro Bild:
    1. Upscaling (kleine Bilder vergrößern, damit die OCR bessere Ergebnisse liefert)
    2. Umwandlung in Graustufen
    3. Rauschentfernung (Non-Local-Means)
    4. Schräglagenkorrektur (Deskewing)

Eingabe:  Bilder (.png, .jpg, .jpeg) aus dem Eingabeordner
Ausgabe:  vorverarbeitete Graustufenbilder im Ausgabeordner (gleicher Dateiname)
"""

import cv2
from typing import Tuple, Union
import numpy as np
import math
import os
from deskew import determine_skew


def rotate(image: np.ndarray, angle: float, background: Union[int, Tuple[int, int, int]]) -> np.ndarray:
    """
    Übernommene Funktion zur Bildrotation
    Quelle: https://github.com/sbrunner/deskew
    Autor: Stéphane Brunner
    Lizenz: MIT License
    """

    old_width, old_height = image.shape[:2]
    angle_radian = math.radians(angle)
    width = abs(np.sin(angle_radian) * old_height) + abs(np.cos(angle_radian) * old_width)
    height = abs(np.sin(angle_radian) * old_width) + abs(np.cos(angle_radian) * old_height)

    image_center = tuple(np.array(image.shape[1::-1]) / 2)
    rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
    rot_mat[1, 2] += (width - old_width) / 2
    rot_mat[0, 2] += (height - old_height) / 2
    return cv2.warpAffine(image, rot_mat, (int(round(height)), int(round(width))), borderValue=background)

# Pfade
folder_path = "C:/Users/eingabeordner"
folder_outpath = "C:/Users/ausgabeordner"

# Ausgabeordner anlegen, falls er noch nicht existiert
os.makedirs(folder_outpath, exist_ok=True)

for filename in os.listdir(folder_path):
    # Nur unterstützte Bildformate verarbeiten
    if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        continue

    img_path = os.path.join(folder_path, filename)
    img_outpath = os.path.join(folder_outpath, filename)

    img = cv2.imread(img_path)

    # Nicht lesbare Dateien überspringen
    if img is None:
        print(f"Datei nicht lesbar, übersprungen {filename}")
        continue

    # Upscaling auf 2400 p
    scale = float(np.clip(2400 / max(img.shape), 1.0, 3.0))
    img_large = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)

    # Umwandlung in Graustufen
    img_gray = cv2.cvtColor(img_large, cv2.COLOR_BGR2GRAY)

    # Entrauschen mit Non-Local-Means
    img_clean = cv2.fastNlMeansDenoising(img_gray, None, h=7, templateWindowSize=7,
                                         searchWindowSize=21)

    # Drehen
    # determine_skew liefert die Schräglage in Grad (bis 45 Grad)
    winkel = determine_skew(img_clean)
    img_final = img_clean

    if winkel is not None and winkel != 0.0:
        img_final = rotate(img_final, winkel, background=255)

    # Ergebnis speichern
    cv2.imwrite(img_outpath, img_final)
