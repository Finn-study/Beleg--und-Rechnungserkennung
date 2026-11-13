"""
Datenaugmentierung aller Belege und Rechnungen. Ausgenommen hiervon wurden in diesem Projekt eine Gruppe von
bereits augmentierten Rechnungen (siehe hierzu augmentation_unscharf.py).

Jedes Bild aus dem Eingabeordner wird mit zufälligen Störungen versehen, die reale Aufnahmebedingen nachahmen.
- schräg fotografiert
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
path_hintergrund = "C:/Users/Platzhalter/hintergrundbilder"

# Pfad für Ausgabebilder anlegen, falls er noch nicht existiert
os.makedirs(path_augmented, exist_ok=True)

# Alle PNG-Dateien im Eingabeordner
image_files = glob.glob(os.path.join(path, "*.png"))

for img_path in image_files:
    filename = os.path.basename(img_path)
    img = cv2.imread(img_path)

    ### 1. Perspektivische Verzerrung ###
    # Wahrscheinlichkeit: 30 %
    # Simuliert ein schräg aufgenommenes Bild
    if random.random() < 0.3:
        h, w = img.shape[:2]
        # Ursprüngliche Eckpunkte
        pts1 = np.float32([[0, 0], [w, 0], [0, h], [w, h]])

        # Maximale Verschiebung der Ecken
        dx = random.randint(10, 50)
        dy = random.randint(10, 50)

        # Verschiebungen nach innen der vier Ecken (nicht nach außen, da sonst ggf. über Bildrand)
        pts2 = np.float32([
            [random.randint(0, dx), random.randint(0, dy)],   # oben-links
            [-random.randint(0, dx), random.randint(0, dy)],  # oben-rechts
            [random.randint(0, dx), -random.randint(0, dy)],  # unten-links
            [-random.randint(0, dx), -random.randint(0, dy)]  # unten-rechts
        ])

        # Transformationsmatrix von Originalecken zu verschobenen Ecken
        matrix = cv2.getPerspectiveTransform(pts1, pts1 + pts2)
        # Leere Randbereiche werden mit Pixeln aufgefüllt
        img = cv2.warpPerspective(img, matrix, (w, h), borderMode=cv2.BORDER_REPLICATE)


    ### 2. Bildrauschen ###
    # Wahrscheinlichkeit: 50 %
    # Gaußsches Rauschen mit zufälliger Stärke
    if random.random() < 0.5:
        noise = np.random.normal(0, random.randint(10, 30), img.shape)
        # Werte auf gültigen Bereich 0-255 begrenzen
        img = np.clip(img + noise, 0, 255).astype(np.uint8)


    ### 3. Rand / Hintergrund hinzufügen ###
    # Wahrscheinlichkeit: 40 %
    # Beleg wird mittig aurf ein zufälliges Hintergrundbild gelegt
    if random.random() < 0.4:
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


    ### 4. Unschärfe ###
    # Wahrscheinlichkeit: 30 %
    # Gaußscher Weichzeichner mit 3x3- oder 5x5-Kernel
    if random.random() < 0.3:
        kernel_size = random.choice([3, 5])
        img = cv2.GaussianBlur(img, (kernel_size, kernel_size),0)


    ### 5. Helligkeitsanpassung / Verlauf ###
    # Wahrscheinlichkeit: 40 %
    # Simuliert ungleichmäßige Beleuchtung
    # Horizontaler Helligkeitsverlauf
    if random.random() < 0.4:
        h, w = img.shape[:2]
        gradient = np.linspace(random.uniform(0.5, 0.8), random.uniform(0.8, 1.2), w)
        gradient = np.tile(gradient, (h, 1))

        # In 50 % der Fälle wird Verlauf gespiegelt
        if random.choice([True, False]):
            gradient = np.fliplr(gradient)

        # Verlauf auf alle drei Farbkanäle übertragen
        gradient_img = np.dstack([gradient] * 3)

        img = np.clip(img * gradient_img, 0, 255).astype(np.uint8)


    ### 6. Schrift ausbleichen ###
    # Wahrscheinlichkeit: 25 %
    # Simuliert verblasste Schrift älterer Rechnungen / Belege
    # Kontrast wird verringert und Helligkeit erhöht
    if random.random() < 0.25:
        alpha = random.uniform(0.6, 0.9)                # Kontrast
        beta = random.randint(20, 60)                   # Helligkeit
        img = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)


    ### 7. Flecken ####
    # Wahrscheinlichkeit: 30 %
    # Simuliert Kafee- oder Fettflecken
    # 1-3 halbtransparente, gelb-bräunliche Kreise
    if random.random() < 0.3:
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
