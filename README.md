# dataExtract

dataExtract è un'applicazione per estrarre informazioni strutturate da documenti data (Documenti di Trasporto) utilizzando la combinazione di OCR (Tesseract) e un modello di linguaggio (LLM). L'applicazione processa file PDF contenenti data, estrae il testo tramite OCR, e poi utilizza un LLM per analizzare il testo e restituire i dati in formato JSON.

## Esecuzione Locale

### Prerequisiti
- Python 3.9 o superiore
- Tesseract OCR installato sul sistema

### Installazione
1. Clonare il repository:
   ```bash
   git clone https://github.com/tuo-username/dataExtract.git
   cd dataExtract
   ```
2. Installare le dipendenze:
   ```bash
   pip install -r requirements.txt
   ```
3. Impostare la variabile d'ambiente:
   - Creare un file `.env` nella directory principale
   - Aggiungere la tua chiave API OpenAI:
     ```env
     OPENAI_API_KEY=la_tua_chiave_api_qui
     ```
4. Eseguire l'applicazione:
   ```bash
   python main.py
   ```

## Esecuzione con Docker

### Prerequisiti
- Docker e Docker Compose installati

### Installazione
1. Clonare il repository (se non già fatto):
   ```bash
   git clone https://github.com/tuo-username/dataExtract.git
   cd dataExtract
   ```
2. Eseguire i container:
   ```bash
   docker-compose up
   ```

### Note Importanti
- Per l'esecuzione locale, Tesseract OCR deve essere installato sul sistema host
- Per l'esecuzione con Docker, Tesseract è preinstallato nel container