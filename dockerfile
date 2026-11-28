FROM python:3.14

WORKDIR /app

# alle Dateien in den Container kopieren
COPY . .

# Systembibliothek für OpenCV
RUN apt-get update && apt-get install -y libglib2.0-0

# PyTorch als CPU-Version
RUN pip install torch==2.15.0 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
RUN pip install -r requirements.txt

# Modelle schon beim Build laden, damit es beim Starten schneller geht
RUN python -c "import easyocr; easyocr.Reader(['de', 'en'], gpu=False)"
RUN python -c "from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification; LayoutLMv3Processor.from_pretrained('Finn-study/layoutlmv3-rechnungserkennung', apply_ocr=False); LayoutLMv3ForTokenClassification.from_pretrained('Finn-study/layoutlmv3-rechnungserkennung')"

ENV HF_HUB_OFFLINE=1
ENV HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD python api.py