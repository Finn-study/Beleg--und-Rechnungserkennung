"""
Nächtliche Batch-Verarbeitung von Belegen und Rechnungen.

Ablauf:
1. Wartet, bis die API (api.py) erreichbar ist.
2. Schickt jedes Bild aus Eingangsordner an API.
3. Speichert jedes Ergebnis, bzw. Fehler als neue Zeile in der Ergebnis-CSV.
4. Verschiebt verarbeitete Bilder nach verarbeitet/, fehlerhafte nach fehler/
5. Beendet sich mit Fehlercode, wenn mindestens ein Bild fehlgeschlagen ist.

Eingabe:  Bilder im Ordner eingang/
Ausgabe:  ergebnisse/ergebnisse.csv, verarbeitet/, fehler/
"""

import os
import csv
import shutil
import sys
import time
import requests
from datetime import datetime

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
EINGANG_ORDNER = "eingang"
CSV_DATEI = "ergebnisse/ergebnisse.csv"

heute = datetime.now().strftime("%d.%m.%Y")
fehler_anzahl = 0

# Ordner anlegen, falls er noch nicht existiert
os.makedirs(EINGANG_ORDNER, exist_ok=True)
os.makedirs("ergebnisse", exist_ok=True)
os.makedirs("verarbeitet", exist_ok=True)
os.makedirs("fehler", exist_ok=True)


# Warten bis API gestartet ist
api_started = False
for i in range(60):
    try:
        r = requests.get(API_URL + "/docs", timeout=5)
        if r.status_code == 200:
            api_started = True
            break
    except:
        pass
    time.sleep(5)

if api_started == False:
    sys.exit("API ist nicht erreichbar")

# Überschriften schreiben, sofern die CSV noch nicht existiert
if not os.path.exists(CSV_DATEI):
    with open(CSV_DATEI, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Verarbeitet_am", "Dateiname", "Datum", "Rechnungsnummer", "Kundennummer", "Steuer_1", "Steuer_2", "Gesamtsumme", "Fehlermeldung"])

# Alle Dateien im Eingangsordner durchgehen
for dateiname in os.listdir(EINGANG_ORDNER):
    name_klein = dateiname.lower()
    if not (name_klein.endswith(".jpg") or name_klein.endswith(".jpeg") or name_klein.endswith(".png")):
        continue

    pfad = EINGANG_ORDNER + "/" + dateiname

    try:
        with open(pfad, "rb") as bild:
            antwort = requests.post(API_URL + "/extract", files={"file": bild}, timeout=600)

        daten = antwort.json()
        if antwort.status_code == 200 and daten.get("status") == "success":
            erg = daten["ergebnisse"]

            with open(CSV_DATEI, "a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow([
                    heute,
                    dateiname,
                    erg["Datum"],
                    erg["Rechnungsnummer"],
                    erg["Kundennummer"],
                    erg["Steuer_1"],
                    erg["Steuer_2"],
                    erg["Gesamtsumme"]
                ])

            # Bild nach erfolgreicher Verarbeitung aus dem Ordner löschen
            shutil.move(pfad, "verarbeitet/" + dateiname)
        else:
            # Fehlerantwort der API an den except-Block weitergeben
            raise Exception(antwort.text)

    except Exception as e:
        # Fehler in der CSV festhalten und Bild aussortieren. Sonst wird es jedes mal erneut versucht
        fehler_anzahl += 1
        with open(CSV_DATEI, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow([heute, dateiname, "", "", "", "", "", "", str(e)])
        shutil.move(pfad, "fehler/" + dateiname)

# Fehlercode, damit GitHub den Lauf als fehlgeschlagen markiert
if fehler_anzahl > 0:
    sys.exit(1)
