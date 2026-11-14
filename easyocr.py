"""
OCR-Vorverarbeitung für das LayoutLMv3-Training mit EasyOCR

Ablauf pro Bild:
    1. Bild aus dem Eingabeordner einlesen.
    2. Wörter und Positionen mit EasyOCR erkennen.
    3. Positionen auf den Wertebereich 0 bis 1000 normalisieren (wie in api.py).
    4. Wörter und Boxen in der Ergebnisliste sammeln.

Das Ergebnis wird als eine JSON-Datei gespeichert. Pro Bild enthält sie den Dateinamen, die erkannten Wörter und
die dazugehörigen Boxen [x_min, y_min, x_max, y_max]. Die Konfidenz von EasyOCR wird nicht gespeichert.
"""

import easyocr
import os
import cv2
import json

# Ordner mit vorverarbeiteten Bildern
folder_path = "C:/Users/platzhalter"
# Ausgabedatei
json_outpath = "C:/Users/platzhalter/ocr_layoutlm.json"

# gpu=False: Läuft bewusst auf der CPU wegen Reproduzierbarkeit.
# Beim ersten Start lädt EasyOCR die Erkennungsmodelle aus dem Internet herunter.
reader = easyocr.Reader(['de', 'en'], gpu=False)

# Liste mit einem Eintrag pro Bild (Dateiname, Wörter, Boxen)
alle_bilder_daten = []

for filename in os.listdir(folder_path):
    # Nur Bilddateien verarbeiten, alles andere im Ordner überspringen
    if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        continue

    # Bild einlesen, um Höhe und Breite für die Normalisierung zu erhalten
    img_path = os.path.join(folder_path, filename)
    img = cv2.imread(img_path)
    hoehe, breite = img.shape[:2]

    # EasyOCR: liefert Box, Text und Konfidenz
    results = reader.readtext(img_path, detail=1)

    # Ergebnis dieses Bildes
    bild_daten = {
        "file_name": filename,
        "words": [],
        "bboxes": []
    }

    # Ergebnisse für LayoutLMV3 aufbereiten
    for (bbox, text, prob) in results:
        x_min = min([punkt[0] for punkt in bbox])
        x_max = max([punkt[0] for punkt in bbox])
        y_min = min([punkt[1] for punkt in bbox])
        y_max = max([punkt[1] for punkt in bbox])

        # Normalisierung für LayoutLMv3 auf 0 bis 1000
        norm_x_min = int(1000 * (x_min / breite))
        norm_x_max = int(1000 * (x_max / breite))
        norm_y_min = int(1000 * (y_min / hoehe))
        norm_y_max = int(1000 * (y_max / hoehe))

        # Werte auf 0 bis 1000 begrenzen
        norm_box = [
            max(0, min(1000, norm_x_min)),
            max(0, min(1000, norm_y_min)),
            max(0, min(1000, norm_x_max)),
            max(0, min(1000, norm_y_max))
        ]

        bild_daten["words"].append(text)
        bild_daten["bboxes"].append(norm_box)

    alle_bilder_daten.append(bild_daten)

# Als JSON speichern
with open(json_outpath, "w", encoding="utf-8") as f:
    json.dump(alle_bilder_daten, f, ensure_ascii=False, indent=4)
