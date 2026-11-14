"""
Auswertung des feingetunten LayoutLMv3-Modells auf den Testdaten.

Ablauf:
    1. Feingetuntes Modell und Processor aus dem Ordner final_model laden
    2. Annotationen den Bildern des Ordners test zuordnen
    3. Modell auf alle Testbelege anwenden
    4. Precision, Recall und F1 (seqeval) berechnen, insgesamt und pro Feld
    5. Ergebnisse als JSON- und CSV-Datei speichern

Eingabe:  JSON-Annotationsdatei, vorverarbeitete Testbilder (Ordner test),
          feingetuntes Modell (<Modellpfad>/final_model)
Ausgabe:  test_ergebnisse.json (alle Kennzahlen und Angaben zum Lauf)
          test_ergebnisse.csv (Precision, Recall, F1 pro Feld und insgesamt)

Zu bewertende Felder: Datum, Rechnungsnummer, Kundennummer, Steuern, Gesamtsumme
"""

import os
import json
import csv
from datetime import datetime
from pathlib import Path
import evaluate
import numpy as np
import torch
from PIL import Image
from transformers import (
    LayoutLMv3ForTokenClassification,
    LayoutLMv3Processor,
    TrainingArguments,
    Trainer,
    DefaultDataCollator
)

# ===== #
# Pfade #
# ===== #

# JSON-Datei mit den Annotationen
ann_file = "C:/Users/platzhalter/layoutlm.json"
# Pfad zum feingetunten LayoutLMv3 Modell
model_path = "C:/Users/platzhalter/layoutlmv3_finetuned/final_model"
# Pfad zu den Ordnern train, val und test, in denen die vorverarbeiteten Bilder liegen
img_path = Path("C:/Users/platzhalter")
# Ordner, in dem die Ergebnisse gespeichert werden
results_path = "C:/Users/platzhalter"

os.makedirs(results_path, exist_ok=True)

# ============================ #
# Modell und Processor laden   #
# ============================ #

# Der Processor wurde beim Training zusammen mit dem Modell gespeichert
# apply_ocr = False: Texterkennung hat EasyOCR übernommen. Der Processor würde Tesseract verwenden.
processor = LayoutLMv3Processor.from_pretrained(model_path, apply_ocr=False)
model = LayoutLMv3ForTokenClassification.from_pretrained(model_path)

# Labels direkt aus dem Modell lesen, damit sie sicher zum Training passen
id2label = {int(i): l for i, l in model.config.id2label.items()}
label2id = {l: i for i, l in id2label.items()}
label_list = [id2label[i] for i in range(len(id2label))]

# =========== #
# Daten laden #
# =========== #

# Annotationen einlesen
with open(ann_file, encoding="utf-8") as f:
    by_name = {e["file_name"]: e for e in json.load(f)}

def load_split(folder):
    """
    Verknüpft Bilder eines Ordners mit den Annotationen.
    Es werden nur Bilder berücksichtigt, die einen Eintrag in der JSON-Datei haben.
    """
    return [{**by_name[p.name], "image_path": str(p)}
            for p in folder.iterdir()
            if p.suffix.lower() in {".png", ".jpg", ".jpeg"} and p.name in by_name]

test_data = load_split(img_path / "test")

# ======= #
# Dataset #
# ======= #

class BonDataset(torch.utils.data.Dataset):
    """Stellt pro Beleg die tokenisierten Eingaben für LayoutLMv3 bereit"""
    def __init__(self, data):
        self.data = data

    def __len__(self):
        return len(self.data)

    def __getitem__(self, i):
        e = self.data[i]
        image = Image.open(e["image_path"]).convert("RGB")

        # Bild, Wörter und Labels in Modelleingaben umwandeln
        # Länge fest auf 512 Tokens
        enc = processor(
            image,
            e["words"],
            boxes=e["bboxes"],
            word_labels=[label2id[l] for l in e["labels"]],
            truncation=True,
            padding="max_length",
            max_length=512,
            return_tensors="pt",
        )
        return {k: v.squeeze(0) for k, v in enc.items()}

test_ds = BonDataset(test_data)

# ========== #
# Vorhersage #
# ========== #

# Nur für Auswertung
args = TrainingArguments(
    output_dir=results_path,
    per_device_eval_batch_size=2,
    report_to="none",
)

trainer = Trainer(
    model=model,
    args=args,
    data_collator=DefaultDataCollator(),
)

# Modell auf alle Testbelege anwenden
prediction = trainer.predict(test_ds)

# Modellausgabe und tatsächliche Labels holen
logits = prediction.predictions[0] if isinstance(prediction.predictions, tuple) else prediction.predictions
labels = prediction.label_ids

# Pro Token die Klasse mit höchster Wahrscheinlichkeit wählen
preds = np.argmax(logits, axis=2)

# ======== #
# Metriken #
# ======== #

# Tokens mit dem Label -100 werden nicht mitgezählt.
# Vorhersagen und Referenzen werden in Label-Namen umgewandelt
true_preds = [
    [label_list[p_] for p_, l in zip(pr, la) if l != -100]
    for pr, la in zip(preds, labels)
]
true_labels = [
    [label_list[l] for p_, l in zip(pr, la) if l != -100]
    for pr, la in zip(preds, labels)
]

# seqeval: Standardmetrik für Sequenzmarkierung
metric = evaluate.load("seqeval")
r = metric.compute(predictions=true_preds, references=true_labels)

# Ergebnisse pro Feld und insgesamt zusammenstellen
fields = {}
for key, value in r.items():
    if not key.startswith("overall_"):
        fields[key] = {
            "precision": float(value["precision"]),
            "recall": float(value["recall"]),
            "f1": float(value["f1"]),
            "support": int(value["number"]),
        }

overall = {
    "precision": float(r["overall_precision"]),
    "recall": float(r["overall_recall"]),
    "f1": float(r["overall_f1"]),
    "accuracy": float(r["overall_accuracy"]),
}

# ================== #
# Ergebnisse sichern #
# ================== #

# JSON: alle Kennzahlen und Angaben zum Lauf
results = {
    "datum": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "modell": model_path,
    "anzahl_testbelege": len(test_ds),
    "gesamt": overall,
    "pro_feld": fields,
}
with open(os.path.join(results_path, "test_ergebnisse.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

# CSV: eine Zeile pro Feld und eine Zeile für das Gesamtergebnis
with open(os.path.join(results_path, "test_ergebnisse.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow(["Feld", "Precision", "Recall", "F1", "Anzahl"])
    for name, v in fields.items():
        writer.writerow([name, round(v["precision"], 4), round(v["recall"], 4),
                         round(v["f1"], 4), v["support"]])
    writer.writerow(["GESAMT", round(overall["precision"], 4), round(overall["recall"], 4),
                     round(overall["f1"], 4), sum(v["support"] for v in fields.values())])
