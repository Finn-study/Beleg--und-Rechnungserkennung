"""
Automatische Label-Zuordnung für das Training von LayoutLMv3.
Ablauf pro Beleg:
    1. OCR-Wörter (EasyOCR-Ausgabe) aus der JSON-Datei einlesen
    2. Lösungswerte (Datum, Rechnungsnummer, Kundennummer, Steuern, Gesamtsumme) aus der CSV-Datei holen
    3. Jedes OCR-Wort mit den Lösungswerten abgleichen (exakt, Teilstring oder Ähnlichkeit >= 80 %;
       bei Beträgen zusätzlich mit Korrektur typischer OCR-Verwechslungen)
    4. Passenden Wörtern ein Label zuweisen (B-DATE, B-INV_NO, B-CUST_ID, B-TAX, B-TOTAL),
       alle übrigen Wörter erhalten das Label "O"

Eingabe:  In 4_easyocr erstellte json-Datei und in 1_beleg_generator.py erstellte csv-Datei mit Lösungen
Ausgabe:  json-Datei mit Labels

Ergänzung: Dieses Skript hat aufgrund mangelhafter OCR-Erkennung bedingt funktioniert.
           Es war eine personelle Überarbeitung der json-Datei notwendig.
"""

import json
import pandas as pd
import difflib

# ===== #
# Pfade #
# ===== #

# Pfad zu der in 4_easyocr erstellten json-Datei
json_input = "C:/Users/platzhalter.json"
# Pfad zu der in 1_beleg_generator.py erstellten csv-Datei
csv_input = "C:/Users/platzhalter.csv"
# Pfad zu der neuen JSON-Datei mit Labels
json_output = "C:/Users/platzhalter.json"

# =============== #
# Hilfsfunktionen #
# =============== #

def clean_string(text):
    """Alles in Kleinbuchstaben, entfernt Leerzeichen & Eurozeichen"""
    if pd.isna(text):
        return ""
    return str(text).lower().replace(" ", "").replace("€", "").replace("eur", "")

def correct_ocr_numbers(text):
    """Übersetzt typische OCR-Fehler bei Beträgen zurück in Zahlen."""
    if pd.isna(text): return ""
    text = str(text).replace(" ", "").replace("€", "").replace("eur", "")

    # Dezimal- und Tausendertrennzeichen entfernen
    text = text.replace(".", "").replace(",", "")

    # Häufige Verwechslungen der OCR
    replacements = {'O': '0', 'o': '0', 'S': '5', 's': '5', 'l': '1', 'I': '1', 'B': '8', ',': '.'}
    for char_fehler, zahl in replacements.items():
        text = text.replace(char_fehler, zahl)
    return text

def is_similar(str1, str2, threshold=0.8):
    """
    Prüft, ob sich zwei Wörter zu mind. 80 Prozent ähneln.
    Bei sehr kurzen Wörtern wird exakte Übereinstimmung gefordert.
    """
    if len(str1) < 3 or len(str2) < 3:
        return str1 == str2
    return difflib.SequenceMatcher(None, str1, str2).ratio() >= threshold

# ========= #
# Hauptcode #
# ========= #

# OCR-Ergebnisse laden
with open(json_input, "r", encoding="utf-8") as f:
    daten = json.load(f)

# Lösungen laden
df = pd.read_csv(csv_input, sep=';', dtype=str)

for item in daten:
    file_name = item["file_name"]
    words = item["words"]

    # Standardmäßig ist für EasyOCR jedes Textfeld "O" (kein relevantes Feld)
    labels = ["O"] * len(words)

    # Suche die Lösung für dieses spezifische Bild in der CSV
    row = df[df["Dateiname"] == file_name]

    # Falls eine Zuordnung der Labels nicht möglich ist, behält das Bild ausschließlich Label "O"
    if not row.empty:
        row = row.iloc[0]

        # Tatsächliche Werte für Vergleich vorbereiten
        t_date = clean_string(row["Datum"])
        t_inv_no = clean_string(row["Rechnungsnummer"])
        t_cust_id = clean_string(row["Kundennummer"])

        # Beträge laufen durch die spezielle OCR-Korrektur
        t_tax = correct_ocr_numbers(row["Steuern"])
        t_total = correct_ocr_numbers(row["Gesamtsumme"])

        # Erster Treffer für das Datum erhält Label
        date_found = False
        # Erste Treffer für Rechnungsnummer erhält das Label
        inv_no_found = False
        # Letzter Treffer für Steuer und Gesamtsumme bekommt jeweils das Label
        last_tax_idx = -1
        last_total_idx = -1

        # Abgleich: OCR-Wort vs. CSV-Wert
        for i, word in enumerate(words):
            w_clean = clean_string(word)        # Text-Vergleiche
            w_num = correct_ocr_numbers(word)   # Betrags-Vergleiche

            # DATUM (erster Treffer erhält Label)
            if not date_found and t_date != "":
                if t_date == w_clean or t_date in w_clean or is_similar(t_date, w_clean, 0.8):
                    labels[i] = "B-DATE"
                    date_found = True
                    continue

            # RECHNUNGSNUMMER (erster Treffer erhält Label)
            if not inv_no_found and t_inv_no != "":
                if t_inv_no == w_clean or t_inv_no in w_clean or is_similar(t_inv_no, w_clean, 0.8):
                    labels[i] = "B-INV_NO"
                    inv_no_found = True
                    continue

            # KUNDENNUMMERN (80% Ähnlichkeit ausreichend)
            if t_cust_id != "":
                if t_cust_id == w_clean or t_cust_id in w_clean or is_similar(t_cust_id, w_clean, 0.8):
                    labels[i] = "B-CUST_ID"
                    continue

            # BETRÄGE (Letzter Treffer erhält Label)
            if t_tax != "":
                if t_tax == w_num or t_tax in w_num:
                    last_tax_idx = i

            if t_total != "":
                if t_total == w_num or t_total in w_num:
                    last_total_idx = i

        # Labels für Steuer und Gesamtsumme am jeweils letzten Treffer setzen
        if last_tax_idx != -1:
            labels[last_tax_idx] = "B-TAX"

        if last_total_idx != -1:
            labels[last_total_idx] = "B-TOTAL"

    # Labels am Bild-Eintrag speichern
    item["labels"] = labels

# Ergebnis als json speichern
with open(json_output, "w", encoding="utf-8") as f:
    json.dump(daten, f, ensure_ascii=False, indent=4)
