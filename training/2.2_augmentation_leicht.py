"""
Datenaugmentierung bereits augmentierter Rechnungen.
Alle anderen Belege und Rechnungen wurden mit dem Code in augementation.py augmentiert.

Jedes Bild aus dem Eingabeordner wird mit zufälligen Störungen versehen, die reale Aufnahmebedingen nachahmen.
- Tisch als Hintergrund
- unscharf
- ungleichmäßig beleuchtet
- verblasst
- verschmutzt

Jede Störung wird unabhängig voneinander mit einer festen Wahrscheinlichkeit angewendet.
Das Ergebnis wird mit demselben Dateinamen im Ausgabeorder gespeichert.
"""

import cv2
import numpy as np
import os
import glob
import random

# Pfade
# Pfad zu Originalbildern
path = "C:/Users/Platzhalter"
# Ausgabepfad
path_augmented = "C:/Users/Platzhalter/augmented"
# Pfad Hintergrundbilder
path_hintergrund = "C:/Users/Platzhalter/hintergrund"

# Pfad für Ausgabebilder anlegen, falls er noch nicht existiert
os.makedirs(path_augmented, exist_ok=True)

# Alle PNG-Dateien im Eingabeordner
image_files = glob.glob(os.path.join(path, "*.png"))

for img_path in image_files:
    filename = os.path.basename(img_path)
    img = cv2.imread(img_path)

    ### 1. Rand hinzufügen ###
    # Wahrscheinlichkeit: 10 %
    # Beleg wird mittig auf ein zufälliges Hintergrundbild gelegt
    if random.random() < 0.1:
        # Zufällige Randbreite je Seite (50-300 Pixel)
        top = random.randint(50, 300)
        bottom = random.randint(50, 300)
        left = random.randint(50, 300)
        right = random.randint(50, 300)

        h, w = img.shape[:2]
        new_h = h + top + bottom
        new_w = w + left + right

        bg_files = glob.glob(os.path.join(path_hintergrund, "*.jpg"))

        # Zufälliges Tisch-Bild laden
        bg_img = cv2.imread(random.choice(bg_files))

        # Hintergrundbild auf die exakte neue Gesamtgröße verzerren/skalieren
        bg_img = cv2.resize(bg_img, (new_w, new_h))

        # Beleg/Rechnung in den Hintergrund einsetzen
        bg_img[top:top + h, left:left + w] = img
        img = bg_img


    ### 2. Bildrauschen ###
    # Wahrscheinlichkeit: 30 %
    # Gaußsches Rauschen mit zufälliger Stärke (Standardabweichung 5-12)
    if random.random() < 0.3:
        noise = np.random.normal(0, random.randint(5, 12), img.shape)
        # Werte auf gültigen Bereich 0-255 begrenzen
        img = np.clip(img + noise, 0, 255).astype(np.uint8)


    ### 3. Helligkeitsanpassung / Verlauf ###
    # Wahrscheinlichkeit: 40 %
    # Simuliert ungleichmäßige Beleuchtung
    # Horizontaler Helligkeitsverlauf
    if random.random() < 0.4:
        h, w = img.shape[:2]
        gradient = np.linspace(random.uniform(0.7, 0.9), random.uniform(0.9, 1.1), w)
        gradient = np.tile(gradient, (h, 1))

        # In 50 % der Fälle wird Verlauf gespiegelt
        if random.choice([True, False]):
            gradient = np.fliplr(gradient)

        # Verlauf auf alle drei Farbkanäle übertragen
        gradient_img = np.dstack([gradient] * 3)

        img = np.clip(img * gradient_img, 0, 255).astype(np.uint8)



    ### 4. Schrift ausbleichen ###
    # Wahrscheinlichkeit: 40 %
    # simuliert verblasste Schrift älterer Rechnungen / Belege
    # Kontrast wird verringert und Helligkeit erhöht
    if random.random() < 0.4:
        alpha = random.uniform(0.85, 0.95)              # Kontrast
        beta = random.randint(2, 15)                    # Helligkeit
        img = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)


    ### 5. Flecken ####
    # Wahrscheinlichkeit: 40 %
    # simuliert Kaffee- oder Fettflecken
    # 1-3 halbtransparente, gelb-bräunliche Kreise
    if random.random() < 0.4:
        overlay = img.copy()
        for _ in range(random.randint(1, 3)):
            h, w = img.shape[:2]
            # Zufälliger Mittelpunkt und Radius
            center_x = random.randint(0, w)
            center_y = random.randint(0, h)
            radius = random.randint(20, 80)
            color = (random.randint(100, 150), random.randint(150, 200), random.randint(200, 250))
            cv2.circle(overlay, (center_x, center_y), radius, color, -1)
        # Overlay zu 30 % über das Bild legen
        cv2.addWeighted(overlay, 0.3, img, 0.7, 0, img)


    # Augmentiertes Bild unter demselben Dateinamen speichern
    cv2.imwrite(os.path.join(path_augmented, filename), img)
