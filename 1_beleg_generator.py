"""
Generator für 400 synthetische Belege.

Ablauf pro Bon:
    1. Zufallsdaten erzeugen
    2. Einen von 6 Beleg-Typen befüllen.
    3. Den Text als PNG rendern.
    4. Die tatsächlichen Werte (Datum, Steuer, Gesamtsumme) als Zeile in die CSV schreiben.
"""

import csv
import random
import string

from faker import Faker
from PIL import Image, ImageDraw, ImageFont

# ============= #
# Konfiguration #
# ============= #

# Speicherort der Bilder
ausgabe_ordner = "C:/Users/Platzhalter"
# Speicherort der Labels
csv_pfad = "C:/Users/Platzhalter/labels_bons.csv"
# Sammelliste für die Label-Zeilen
csv_data = []

bildgroesse = (400, 600)
schriftart = "arial.ttf"
schriftgroesse = 14
text_position = (20, 20)

mwst_voll = 0.19        # Regelsteuersatz
mwst_ermaessigt = 0.07  # Ermäßigter Steuersatz

# Gegebener Betrag für den Bon-Typ 1
bar_betrag = 100.00

# Mögliche Leistungen auf den Bon
leistungen = [
    "IT-Beratung (Std.)", "Software-Lizenz", "Server-Hosting", "Webdesign-Paket",
    "SEO-Optimierung", "Datenbank-Migration", "Cloud-Speicher (1TB)", "IT-Support (Remote)", "Mitarbeiter-Schulung",
    "Cybersecurity-Audit", "Schnellhefter", "Druckerpapier (Karton)", "Toner-Kartusche", "Aktenvernichtung", "Porto & Versand",
    "Ergonomischer Bürostuhl", "Fachliteratur", "Schreibwaren-Set",
    "Visitenkarten (500 Stk.)", "Notizbücher (10er Pack)", "Handwerkerstunde",
    "Anfahrtspauschale", "Materialkosten (Pauschale)", "Wartungsvertrag (monatlich)",
    "Reinigungskosten", "Fensterreinigung", "Fachgerechte Entsorgung",
    "Maschinenwartung", "Ersatzteil (Pumpe)", "Montage-Arbeiten",
    "Taxifahrt", "Bahn-Ticket (Flexpreis)", "Hotelübernachtung",
    "Geschäftsessen", "Kaffee & Snacks", "Bewirtungskosten",
    "Parkticket", "Tankfüllung", "Mietwagen (Tagespauschale)",
    "Flugticket (Economy)", "Abendessen", "Werbekampagne (Google Ads)",
    "Social Media Management", "Flyer-Druck (1000 Stk.)", "Werbegeschenke",
    "Messe-Eintrittsticket", "Catering", "Blumenstrauss",
    "Kurierfahrt (Express)", "Steuerberatung", "Kaffee"
    ]

# Faker mit deutschen Daten
fake = Faker('de_DE')

# ====================================== #
# Hauptschleife: ein Durchlauf = ein Bon #
# ====================================== #
for i in range(1, 401):
    filename = f"bon_{i:03d}.png"

    # Fake Daten generieren
    # datum_neu gibt ein zufälliges Datum der letzten 6 Jahre
    datum_neu = fake.date_between("-6y")
    datum = datum_neu.strftime("%d.%m.%Y")
    # datum_2 gibt ein zufälliges Datum bis zu 10 Jahre zurück und ist für Typ 6 als Ablenker
    datum_2 = fake.date_between("-10y", end_date=datum_neu).strftime("%d.%m.%Y")

    uhrzeit = fake.time(pattern='%I:%M')

    # Falsche Firma mit Adresse generieren
    firma = fake.company()
    strasse = fake.street_address()
    ort = fake.city_with_postcode()
    telefon = fake.phone_number()

    # Zufällige Nummer mit 8-12 Ziffern wird als Bon-, Transaktions- bzw. Seriennummern verwendet
    laenge = random.randint(8, 12)
    nummer = "".join(random.choices(string.digits, k=laenge))

    treuepunkte= random.randint(30, 190)





    # Zufällige Leistungen
    leistung_1 = random.choice(leistungen)
    leistung_2 = random.choice(leistungen)
    leistung_3 = random.choice(leistungen)
    leistung_4 = random.choice(leistungen)

    # Brutto & Steuer ermitteln
    # Position 1 mit 19 % USt
    netto_1 = round(random.uniform(5.00, 50.00), 2)
    steuer_1 = round(netto_1 * mwst_voll, 2)
    brutto_1 = round(netto_1 + steuer_1, 2)

    # Position 2 mit 7 % USt
    netto_2 = round(random.uniform(5.00, 50.00), 2)
    steuer_2 = round(netto_2 * mwst_ermaessigt, 2)
    brutto_2 = round(netto_2 + steuer_2, 2)

    # Position 3 mit 19 % USt
    netto_3 = round(random.uniform(5.00, 50.00), 2)
    steuer_3 = round(netto_3 * mwst_voll, 2)
    brutto_3 = round(netto_3 + steuer_3, 2)

    # Position 4 mit 19 % USt
    netto_4 = round(random.uniform(5.00, 50.00), 2)
    steuer_4 = round(netto_4 * mwst_voll, 2)
    brutto_4 = round(netto_4 + steuer_4, 2)

    # Summe über Position 1 und 3. Wird für Typ 3 und 6 verwendet.
    summe_netto_1_3 = netto_1 + netto_3
    summe_brutto_1_3 = brutto_1 + brutto_3
    summe_steuer_1_3 = steuer_1 + steuer_3

    # Summe über alle vier Positionen. Wird in Typ 5 und 6 verwendet
    summe_netto_1_2_3_4 = netto_1 + netto_2 + netto_3 + netto_4
    summe_brutto_1_2_3_4 = brutto_1 + brutto_2 + brutto_3 + brutto_4
    # Summe der Steuer muss nur für die 19 % verwendet werden
    summe_steuer_1_3_4 = steuer_1 + steuer_3 + steuer_4

    # Rückgeld für Typ 1
    bar_zurueck = bar_betrag - brutto_1



    # Textblock 1 Bon mit 19 %: eine Position, Barzahlung mit Rückgeld
    bon_text_1 = f"""
    {firma}
    {strasse}
    {ort}
    
    Datum: {datum}
    ----------------------------------
    1 x {leistung_1}         {brutto_1:.2f} EUR
    ----------------------------------
    
    GESAMTSUMME:             {brutto_1:.2f} EUR
    Bar erhalten             {bar_betrag:.2f} EUR
    Zurück                   {bar_zurueck} EUR
    
    19 % MwSt.:       {steuer_1:.2f} EUR
    
    Vielen Dank für Ihren Besuch!
    """

    # Textblock 2 Bon mit 7 %: eine Position, mit Telefonnummer und Ausstellungsdatum
    bon_text_2 = f"""
        {firma}
        {strasse}
        {ort}

        Ausstellungsdatum: {datum}
        ----------------------------------
        1 x {leistung_2}          {brutto_2:.2f} EUR
        ----------------------------------

        GESAMTSUMME:            {brutto_2:.2f} EUR
        inkl. 7 % MwSt.:        {steuer_2:.2f} EUR


        Nummer für Rückfragen
        {telefon}
        
        Vielen Dank für Ihren Besuch!
        """

    # Textblock 3 Bon: zwei Positionen, mit anderen Tabellenlayout, mit Netto- und Bruttosumme und Treuepunkte
    bon_text_3 = f"""
    {firma}
    {strasse}
    {ort}

    Datum: {datum}
    Uhrzeit: {uhrzeit}
    **********************************************
    2 x {leistung_1}       |EUR {brutto_1:.2f}
    1 x {leistung_3}       |EUR {brutto_3:.2f}
    **********************************************
                            
    SUMME inkl. Mwst.      |EUR {summe_brutto_1_3:.2f}
    **********************************************
                            
    Nettosumme             |EUR {summe_netto_1_3:.2f} 
    MwSt. 19 %             |EUR {summe_steuer_1_3:.2f}

    Für diesen Einkauf erhalten Sie {treuepunkte} Treuepunkte.
    Diese sind unter unserer Webseite einlösbar.
    
    VIELEN DANK!
    """

    # Textblock 4 Bon: eine Position mit Kassenbon-Nr., Brutto,enth. Steuer und Netto
    bon_text_4 = f"""
     Kassenbon Nr. {nummer}
     {firma}
     {strasse}, {ort}

     Artikel                
     ----------------------------------
     {leistung_1}           {brutto_1:.2f} €
     ----------------------------------
     Brutto-Betrag:         {brutto_1:.2f} €                        
     darin enth. 19 % MwSt  {steuer_1:.2f} €
     Netto-Betrag           {netto_1:.2f} €
     
     Zahlungsart: Bar
     Datum der Leistung: {datum}
     
     
     
     Wir danken für Ihren Auftrag!
     """


    # Textblock 5 Bon: vier Positionen und Beleg eines Kleinunternehmers (§ 19 UStG)
    bon_text_5 = f"""
     Quittung
     {firma}
     {strasse}
     {ort}

     Bezeichnung            Gesamt/€
     ----------------------------------
     {leistung_1}             {netto_1:.2f} 
     {leistung_2}             {netto_2:.2f} 
     {leistung_3}             {netto_3:.2f} 
     {leistung_4}             {netto_4:.2f} 
     ----------------------------------
     SUMME:                 {summe_netto_1_2_3_4:.2f}                         
     
     Gemäß § 19 UStG wird keine Umsatzsteuer
     berechnet.
     Zahlungsart: Karte
     Datum der Leistung: {datum}   {uhrzeit}
     
     Transaktionsnummer: {nummer}
     Wir danken für Ihren Auftrag!
     """

    # Textblock 6 Bon: vier Positionen, Zwischensumme und zwei Datumsangaben
    bon_text_6 = f"""
         Quittung / Beleg
         {firma}
         {strasse}
         {ort}
         
         {datum} {uhrzeit}
         Letztes Kassen-Update {datum_2}

         Bezeichnung            Gesamt/€
         ----------------------------------
         1 x {leistung_1}             {brutto_1:.2f} EUR
         1 x {leistung_3}             {brutto_3:.2f} EUR
         Zwischensumme              {summe_brutto_1_3:.2f} EUR
         ----------------------------------
         1 x {leistung_2}             {brutto_2:.2f} EUR
         3 x {leistung_4}             {brutto_4:.2f} EUR
         ----------------------------------
         
         
         SUMME:                 {summe_brutto_1_2_3_4:.2f} EUR
         inkl. 19 % USt         {summe_steuer_1_3_4:.2f} EUR               
         inkl. 7  % USt         {steuer_2:.2f} EUR
         
         Zahlungsart: Karte
         Kassen-Seriennummer: {nummer}
         Besuchen Sie uns bald wieder!
         """


    # Typ abwechselnd wählen
    bon_typ = ((i - 1) % 6) + 1

    # Label-Werte für die CSV
    csv_steuer = 0.0
    csv_gesamt = 0.0
    aktueller_bon_text = ""

    if bon_typ == 1:
        aktueller_bon_text = bon_text_1
        csv_steuer = steuer_1
        csv_gesamt = brutto_1
    elif bon_typ == 2:
        aktueller_bon_text = bon_text_2
        csv_steuer = steuer_2
        csv_gesamt = brutto_2
    elif bon_typ == 3:
        aktueller_bon_text = bon_text_3
        csv_steuer = summe_steuer_1_3
        csv_gesamt = summe_brutto_1_3
    elif bon_typ == 4:
        aktueller_bon_text = bon_text_4
        csv_steuer = steuer_1
        csv_gesamt = brutto_1
    elif bon_typ == 5:
        aktueller_bon_text = bon_text_5
        csv_steuer = 0.00 # keine Steuer auf dem Bon
        csv_gesamt = summe_netto_1_2_3_4
    elif bon_typ == 6:
        aktueller_bon_text = bon_text_6
        csv_steuer = summe_steuer_1_3_4 + steuer_2
        csv_gesamt = summe_brutto_1_2_3_4

    # Bild generieren
    img = Image.new('RGB', bildgroesse, color='white')
    draw = ImageDraw.Draw(img)
    schrift = ImageFont.truetype(schriftart, schriftgroesse)
    draw.text(text_position, aktueller_bon_text, fill='black', font=schrift)

    img.save(f"{ausgabe_ordner}/{filename}")

    # Labelzeilen für diesen Bon anhängen
    csv_data.append({
        "Dateiname": filename,
        "Datum": datum,
        "Rechnungsnummer": "",
        "Kundennummer": "",
        "Steuer": f"{csv_steuer:.2f}",
        "Gesamtsumme": f"{csv_gesamt:.2f}"
    })

    # In die CSV-Datei schreiben
    fieldnames = ["Dateiname", "Datum", "Rechnungsnummer", "Kundennummer", "Steuer", "Gesamtsumme"]
    with open(csv_pfad, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(csv_data)
