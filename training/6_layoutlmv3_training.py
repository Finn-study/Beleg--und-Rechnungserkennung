"""
Feintuning von LayoutLMv3 für die Informationsextraktion aus Belegen und Rechnungen.

Ablauf:
    1. Annotationen (Wörter, Bounding-Boxen, Labels) aus der JSON-Datei laden
    2. Annotationen den vorverarbeiteten Bildern der Ordner train / val / test zuordnen
       (Die Bilder wurden manuell auf die drei Ordner verteilt)
    3. Bild, Wörter und Boxen mit dem LayoutLMv3-Processor in Modelleingaben umwandeln
    4. Vortrainiertes LayoutLMv3 als Token-Klassifikation feintunen
       (Validierung nach jeder Epoche mit seqeval: Precision, Recall, F1)
    5. Bestes Modell (höchster F1-Wert auf den Validierungsdaten) samt Processor speichern

Eingabe:  JSON-Annotationsdatei und vorverarbeitete Bilder (Unterordner train / val / test)
Ausgabe:  feingetuntes Modell und Processor im Ordner <Ausgabepfad>/final_model

Zu extrahierende Felder: Datum, Rechnungsnummer, Kundennummer, Steuern, Gesamtsumme
"""

import os
import json
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
# Pfad für das feingetunte LayoutLMv3 Modell
output_path = "C:/Users/platzhalter/layoutlmv3_finetuned"
# Pfad zu den Ordnern train, val und test, in denen die vorverarbeiteten Bilder liegen
img_path = Path("C:/Users/platzhalter")

# ====== #
# Labels #
# ====== #

label_list = ["O", "B-DATE", "B-INV_NO", "B-CUST_ID", "B-TAX", "B-TOTAL"]

# Zuordnung Label-ID zu Label-Name
id2label = {i: l for i, l in enumerate(label_list)}
label2id = {l: i for i, l in enumerate(label_list)}

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

train_data = load_split(img_path / "train")
val_data = load_split(img_path / "val")
test_data = load_split(img_path / "test")

# ========= #
# Processor #
# ========= #

# Hierdurch wird das Bild skaliert und Wörter in Subword-Tokens tokenisiert
# apply_ocr = False: Texterkennung hat EasyOCR übernommen. Der Processor würde Tesseract verwenden.
processor = LayoutLMv3Processor.from_pretrained("microsoft/layoutlmv3-base",
                                                apply_ocr=False)

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

        # Bild Wörter und Labels in Modelleingaben umwandeln.
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

train_ds = BonDataset(train_data)
val_ds = BonDataset(val_data)
test_ds = BonDataset(test_data)

# ====== #
# Modell #
# ====== #

# Vortrainiertes LayoutLMv3
model = LayoutLMv3ForTokenClassification.from_pretrained(
    "microsoft/layoutlmv3-base",
    num_labels=len(label_list),
    id2label=id2label,
    label2id=label2id
)

# ======== #
# Metriken #
# ======== #

# seqeval: Standardmetrik für Sequenzmarkierung
metric = evaluate.load("seqeval")

def compute_metrics(p):
    """
    Berechnet Precision, Recall und F1 für die Validierungsdaten.
    """
    # Modellausgabe und tatsächliche Labels holen
    logits = p.predictions[0] if isinstance(p.predictions, tuple) else p.predictions
    labels = p.label_ids

    # Pro Token die Klasse mit höchsten Wahrscheinlichkeit wählen
    preds = np.argmax(logits, axis=2)

    # Vorhersagen und Referenzen in Label-Namen umwandeln
    true_preds = [
        [label_list[p_] for p_, l in zip(pr, la) if l != -100]
        for pr, la in zip(preds, labels)
    ]
    true_labels = [
        [label_list[l] for p_, l in zip(pr, la) if l != -100]
        for pr, la in zip(preds, labels)
    ]

    r = metric.compute(predictions=true_preds, references=true_labels)
    return {
        "precision": r["overall_precision"],
        "recall": r["overall_recall"],
        "f1": r["overall_f1"]
    }

# ======== #
# Training #
# ======== #

args = TrainingArguments(
    output_dir=output_path,
    num_train_epochs=15,
    eval_strategy="epoch",
    learning_rate=2e-5,
    per_device_train_batch_size=2,
    per_device_eval_batch_size=2,
    weight_decay=0.01,
    logging_steps=10,
    save_strategy="epoch",          # Checkpoint nach jeder Epoche
    load_best_model_at_end=True,    # am Ende den Checkpoint mit dem besten F1 laden
    metric_for_best_model="f1"
)

# Fasst die einzelnen Beispiele zu Batches zusammen
data_collator = DefaultDataCollator()

trainer = Trainer(
    model=model,
    args=args,
    train_dataset=train_ds,
    eval_dataset=val_ds,
    data_collator=data_collator,
    compute_metrics=compute_metrics,
)

# Training starten
trainer.train()

# Bestes Modell und Processor speichern
trainer.save_model(os.path.join(output_path, "final_model"))
processor.save_pretrained(os.path.join(output_path, "final_model"))
