from fastapi import FastAPI, UploadFile, File, HTTPException
import easyocr
from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification
import re
import cv2
import numpy as np
import math
from typing import Tuple, Union
from deskew import determine_skew
import torch
import uvicorn
from PIL import Image



# ============================ #
# FUNKTION zum POST-PROCESSING #
# ============================ #
def clean_extracted_text(label, text, context=None):
    """
    Bereinigt den Rohtext, den das Modell einem Feld zugeordnet hat und bereinigt das Format.

    label: Label des Feldes (B-DATE, B-TOTAL, B-TAX, B-INV_NO, B-CUST_ID)
    text: Rohtext, der diesem Label zugeordnet wurde
    context: Bereinigte Werte anderer Felder, damit diese nicht ebenfalls anderen Labels zugeordnet werden.
    :return: Bereinigter Wert oder None, wenn kein gültiger Wert erkannt wurde.
    """
    if context is None:
        context = {}

    # Hilfsfunktion für Beträge
    def extract_amounts(t):
        # Datum und Prozentwerte entfernen
        t = re.sub(r'\d{1,2}\s?[./-]\s?\d{1,2}\s?[./-]\s?\d{2,4}', ' ', t)
        t = re.sub(r'\d{1,3}(?:[.,]\d+)?\s*%', ' ', t)

        # Sucht Zahlenblöcke. Ein Leerzeichen darf im Block enthalten sein.
        gruppen = re.findall(r'\d[\d.,;:]*(?: [\d.,;:]+)*', t)
        betraege = []
        for g in gruppen:
            # Alles außer Ziffern wird verworfen
            # Letzten zwei Ziffern gelten immer als Cent
            ziffern = re.sub(r'\D', '', g)
            if not ziffern:
                continue

            euro = ziffern[:-2] or "0"
            cent = ziffern[-2:].zfill(2)

            # Tausendertrennzeichen hinzufügen (z.B. 1077,00 zu 1.077,00)
            if len(euro) > 3:
                euro = f"{euro[:-3]}.{euro[-3:]}"

            betraege.append(f"{euro},{cent} €")
        return betraege

    def finde_nummer(t, ausschliessen=None):
        """
        Hilfsfunktion für Rechnungs- und Kundennummer.
        Gibt das erste Wort mit mindestens einer Ziffer zurück
        """
        # Doppelpunkte wie Leerzeichen behandeln, damit "Nr.:4711" in "Nr." und "4711" zerfällt
        for wort in t.replace(":", " ").split():
            wort = wort.strip(".,;-")
            if not re.search(r'\d', wort):
                continue

            # Datumsangaben und ausgeschlossene Werte überspringen
            if re.fullmatch(r'\d{1,2}[./-]\d{1,2}[./-]\d{2,4}', wort) or wort == ausschliessen:
                continue

            return wort
        return None

    # Datum
    if label == "B-DATE":
        # Zuerst prüfen, ob bereits ein sauberes Format vorliegt (z.B. 12.04.2025 oder 12-04-2025)
        match_standard = re.search(r'\d{2}[./-]\d{2}[./-]\d{2,4}', text)
        if match_standard:
            return re.sub(r'[/-]', '.', match_standard.group(0))

        # Fallback, falls kein sauberes Format vorliegt
        digits = re.sub(r'\D', '', text)
        # Wenn exakt 8 Ziffern gefunden wurden (z.B. "1204 2025" wird zu "12042025")
        if len(digits) == 8:
            return f"{digits[:2]}.{digits[2:4]}.{digits[4:]}"
        # Wenn exakt 6 Ziffern gefunden wurden
        elif len(digits) == 6:
            return f"{digits[:2]}.{digits[2:4]}.{digits[4:]}"
        # Wenn kein Datum in den Labels erkannt wird, wird nichts ausgegeben.
        return None

    # Summe
    elif label == "B-TOTAL":
        betraege = extract_amounts(text)
        if betraege:
            # Nimmt den höchsten gefundenen Wert.
            floats = [float(b.replace(".", "").replace(",", ".").replace(" €", "")) for b in betraege]
            max_index = floats.index(max(floats))
            return betraege[max_index]

        return None

    # Steuern
    elif label == "B-TAX":
        betraege = extract_amounts(text)
        # Doppelte Beträge entfernen
        eindeutige = list(dict.fromkeys(betraege))

        # Prüft, ob die Gesamtsumme fälschlicherweise ebenfalls als Steuer erkannt wurde
        summe = context.get("B-TOTAL")
        if summe in eindeutige:
            eindeutige.remove(summe)

        # Gibt maximal 2 Steuerwerte als Liste zurück (19 % und 7 %)
        return eindeutige[:2]

    # Rechnungsnummer
    elif label == "B-INV_NO":
        return finde_nummer(text)

    # Kundennummer
    elif label == "B-CUST_ID":
        return finde_nummer(text, ausschliessen=context.get("B-INV_NO"))


# =============== #
# Setup & Modelle #
# =============== #
model_path = "C:/Users/Platzhalter"

# apply_ocr = False: Texterkennung übernimmt EasyOCR, nicht der Processor, welcher Tesseract verwenden würde.
processor = LayoutLMv3Processor.from_pretrained(model_path, apply_ocr=False)
model = LayoutLMv3ForTokenClassification.from_pretrained(model_path)
model.eval()

app = FastAPI()

# gpu=False: Läuft bewusst auf der CPU wegen Reproduzierbarkeit.
# Beim ersten Start lädt EasyOCR die Erkennungsmodelle aus dem Internet herunter.
reader = easyocr.Reader(['de', 'en'], gpu=False)


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


def ausrichten(img):
    """
    Dreht das Bild in 90-Grad-Schritten, sodass der Text aufrecht ist.
    EasyOCR wird auf allen vier Drehungen ausgeführt. Die Drehung mit der besten Erkennung wird gewählt.
    """
    kandidaten = [
        img,
        cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE),
        cv2.rotate(img, cv2.ROTATE_180),
        cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE),
    ]

    def bewertung(bild):
        # Summe der Confidence
        return sum(prob for (_, _, prob) in reader.readtext(bild, detail=1))

    return max(kandidaten, key=bewertung)



# === #
# API #
# === #
@app.post("/extract")
async def extract_invoice_data(file: UploadFile = File(...)):
    # 1. Bild einlesen
    inhalt = await file.read()
    nparr = np.frombuffer(inhalt, np.uint8)
    img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # None zurückgeben, wenn kein lesbares Bild.
    if img_cv is None:
        raise HTTPException(status_code=400, detail="Datei nicht lesbar.")

    # 2. Bild Vorverarbeitung
    # 2.1 Upscaling auf 2400 px
    scale = float(np.clip(2400 / max(img_cv.shape), 1.0, 3.0))
    img_large = cv2.resize(img_cv, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)

    # 2.2 Umwandlung in Graustufen
    img_gray = cv2.cvtColor(img_large, cv2.COLOR_BGR2GRAY)

    # 2.3 Entrauschen mit Non-Local-Means
    img_clean = cv2.fastNlMeansDenoising(img_gray, None, h=7, templateWindowSize=7,
                                         searchWindowSize=21)

    # 2.4 Drehen
    # Grobausrichtung in 90-Grad-Schritten bestimmen
    img_clean = ausrichten(img_clean)

    # determine_skew liefert die Schräglage in Grad (bis 45 Grad)
    winkel = determine_skew(img_clean)
    img_final = img_clean
    if winkel is not None and winkel != 0.0:
        img_final = rotate(img_final, winkel, background=255)

    # Bildmaße nach der Vorverarbeitung (für die Normalisierung)
    bild_hoehe, bild_breite = img_final.shape[:2]


    # 3. EasyOCR: liefert Box, Text und Konfidenz
    results = reader.readtext(img_final, detail=1)

    words = []
    bboxes = []

    # Ergebnisse für LayoutLMV3 aufbereiten
    for (bbox, text, _) in results:
        x_min = min([punkt[0] for punkt in bbox])
        x_max = max([punkt[0] for punkt in bbox])
        y_min = min([punkt[1] for punkt in bbox])
        y_max = max([punkt[1] for punkt in bbox])

        # Normalisierung für LayoutLMv3 auf 0 bis 1000
        norm_x_min = int(1000 * (x_min / bild_breite))
        norm_x_max = int(1000 * (x_max / bild_breite))
        norm_y_min = int(1000 * (y_min / bild_hoehe))
        norm_y_max = int(1000 * (y_max / bild_hoehe))

        # Werte auf 0 bis 1000 begrenzen
        norm_box = [
            max(0, min(1000, norm_x_min)),
            max(0, min(1000, norm_y_min)),
            max(0, min(1000, norm_x_max)),
            max(0, min(1000, norm_y_max))
        ]

        words.append(text)
        bboxes.append(norm_box)


    if not words:
        return {
            "status": "error",
            "dateiname": file.filename,
            "message": "Kein Text auf dem Bild gefunden."}


    # 4. LayoutLMv3 erwartet Bild mit drei Farbkanälen, daher Graustufen wieder in RGB
    img_rgb = cv2.cvtColor(img_final, cv2.COLOR_GRAY2RGB)
    img_pil = Image.fromarray(img_rgb)

    # Maximale Textlänge auf 512 Tokens gesetzt
    encoding = processor(
        img_pil, words, boxes=bboxes, return_tensors="pt",
        truncation=True, padding="max_length", max_length=512
    )

    with torch.no_grad():
        outputs = model(**encoding)

    # Label-ID mit der höchsten Wahrscheinlichkeit für jedes Token
    vorhersagen = outputs.logits.argmax(-1).squeeze().tolist()

    # Box jedes Tokens
    token_boxes = encoding["bbox"].squeeze().tolist()

    # 5. Ergebnisse sammeln
    extrahiert = {
        "Datum": None,
        "Rechnungsnummer": None,
        "Kundennummer": None,
        "Steuer_1": None,
        "Steuer_2": None,
        "Gesamtsumme": None
    }

    # Vom Modell vorhergesagte Wörter
    gefundene_werte = {
        "B-DATE": [],
        "B-INV_NO": [],
        "B-CUST_ID": [],
        "B-TAX": [],
        "B-TOTAL": []
    }

    box_zu_wort = {}
    for wort, box in zip(words, bboxes):
        box_koordinaten = tuple(box)
        box_zu_wort[box_koordinaten] = wort

    # 6. Token-Vorhersagen den Labels zuordnen
    for vorhersage_id, box in zip(vorhersagen, token_boxes):
        label = model.config.id2label[vorhersage_id]

        # Überspringt Label "O"
        if label == "O" or label not in gefundene_werte or box == [0, 0, 0, 0]:
            continue

        box_koordinaten = tuple(box)
        if box_koordinaten in box_zu_wort:
            original_wort = box_zu_wort[box_koordinaten]

            # Jedes Wort wird pro Label nur einmal gesammelt
            if original_wort not in gefundene_werte[label]:
                gefundene_werte[label].append(original_wort)

    # 7. Felder bereinigen
    # Gesamtsumme und Rechnungsnummer werden zuerst bereinigt,
    # da sie als Kontext für Steuer und Kundennummer benötigt werden
    text_datum = " ".join(gefundene_werte["B-DATE"])
    text_summe = " | ".join(gefundene_werte["B-TOTAL"]) # Mit Trennzeichen zur sauberen Trennung von Beträgen
    text_rechnung = " ".join(gefundene_werte["B-INV_NO"])
    extrahiert["Datum"] = clean_extracted_text("B-DATE", text_datum)
    extrahiert["Gesamtsumme"] = clean_extracted_text("B-TOTAL", text_summe)
    extrahiert["Rechnungsnummer"] = clean_extracted_text("B-INV_NO", text_rechnung)

    # Kontext für Steuer und Kundennummer
    kontext_wissen = {
        "B-TOTAL": extrahiert["Gesamtsumme"],
        "B-INV_NO": extrahiert["Rechnungsnummer"]
    }

    # Als Datum erkannte Wörter entfernen
    gefundene_werte["B-TAX"] = [w for w in gefundene_werte["B-TAX"] if w not in gefundene_werte["B-DATE"]]

    # Steuer und Kundennummer bereinigen
    text_steuer = " | ".join(gefundene_werte["B-TAX"])
    text_kunde = " ".join(gefundene_werte["B-CUST_ID"])
    steuern = clean_extracted_text("B-TAX", text_steuer, context=kontext_wissen)
    extrahiert["Steuer_1"] = steuern[0] if len(steuern) > 0 else None
    extrahiert["Steuer_2"] = steuern[1] if len(steuern) > 1 else None
    extrahiert["Kundennummer"] = clean_extracted_text("B-CUST_ID", text_kunde, context=kontext_wissen)

    return {
        "status": "success",
        "dateiname": file.filename,
        "ergebnisse": extrahiert
    }

if __name__ == "__main__":
    print("Starte API Server auf http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
