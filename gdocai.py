import os
import sys
import json
import datetime
from google.cloud import documentai_v1 as documentai
from google.api_core.client_options import ClientOptions
from dotenv import load_dotenv

# Importa tkinter e filedialog per il dialogo di selezione file
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox # Per mostrare messaggi di errore grafici


# Carica le variabili d'ambiente 
# dal file .env (se presente).  
load_dotenv()

# --- Configurazione Credenziali Google Cloud ---
credentials_file_name = os.getenv("GOOGLE_CREDENTIALS_FILE")

if credentials_file_name:
    credentials_path = os.path.join(os.getcwd(), credentials_file_name)
    if os.path.exists(credentials_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
        print(f"Credenziali impostate da: {credentials_path}")
    else:
        print(f"Attenzione: File delle credenziali '{credentials_path}' non trovato.")
        print("Assicurati che il file JSON della chiave di servizio sia nella root del progetto.")
else:
    print("Attenzione: GOOGLE_CREDENTIALS_FILE non specificato nel file .env.")
    print("Il client cercherà le credenziali con il metodo Application Default Credentials (ADC).")

# --- Configurazione Document AI ---
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
LOCATION = os.getenv("DOCUMENT_AI_LOCATION", "eu")
PROCESSOR_ID = os.getenv("DOCUMENT_AI_PROCESSOR_ID")

# Nuove variabili per field_mask e process_options dal .env
# Default: None (non applicato)
FIELD_MASK = os.getenv("DOCUMENT_AI_FIELD_MASK", None)
# Default: 0 significa processa tutte le pagine. Se 1, processa solo la prima pagina.
PROCESS_FIRST_PAGE_ONLY = os.getenv("DOCUMENT_AI_PROCESS_FIRST_PAGE_ONLY", "0").lower() == "1"


if not PROJECT_ID:
    messagebox.showerror("Errore di Configurazione", "Variabile d'ambiente GOOGLE_CLOUD_PROJECT_ID non impostata nel file .env o nel tuo ambiente.")
    sys.exit(1)
if not PROCESSOR_ID:
    messagebox.showerror("Errore di Configurazione", "Variabile d'ambiente DOCUMENT_AI_PROCESSOR_ID non impostata nel file .env o nel tuo ambiente. Dovrebbe essere l'ID numerico del tuo processore specifico.")
    sys.exit(1)

PROCESSOR_PATH = f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}"

client_options = ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")
client = documentai.DocumentProcessorServiceClient(client_options=client_options)


# DEFINIZIONA FUNZIONI
def extract_text(layout, document):
    """Estrae il testo da un layout senza usare HasField."""
    if not layout.text_anchor.text_segments:
        return ""

    text = ""
    for segment in layout.text_anchor.text_segments:
        start_index = getattr(segment, "start_index", 0)
        end_index = segment.end_index
        text += document.text[start_index:end_index]
    return text.strip()

def rimappa_json(document_proto):
    risultato = {
        "fornitore": "",
        "numero_documento": "",
        "data_documento": "",
        "riga": []
    }

    # Estrazione entità principali ---
    if document_proto.entities:
        for entity in document_proto.entities:
            name = entity.type_.lower()
            value = entity.mention_text.strip() if entity.mention_text else ""
            if "fornitore" in name:
                risultato["fornitore"] = value
            elif "numero" in name:
                risultato["numero_documento"] = value
            elif "data" in name:
                risultato["data_documento"] = value

    # Estrazione righe dalla tabella ---
    for page in document_proto.pages:
        for table in page.tables:
            # Estrai intestazioni
            header = []
            if table.header_rows:
                for cell in table.header_rows[0].cells:
                    header.append(extract_text(cell.layout, document_proto).lower())

            # Estrai righe corpo
            for row in table.body_rows:
                values = [extract_text(cell.layout, document_proto) for cell in row.cells]
                riga_dict = dict(zip(header, values))

                nuova_riga = {
                    "progressivo_riga": riga_dict.get("progressivo", ""),
                    "riferimento": riga_dict.get("riferimento", ""),
                    "codice_articolo": riga_dict.get("codice_articolo", ""),
                    "descrizione": riga_dict.get("descrizione", ""),
                    "quantità": float(riga_dict.get("quantità", "0").replace(",", ".") or 0),
                    "prezzo": float(riga_dict.get("prezzo", "0").replace(",", ".") or 0)
                }

                risultato["riga"].append(nuova_riga)

    return risultato



def process_document(file_path: str):
    """
    Invia un documento PDF a Google Document AI e stampa il risultato JSON completo.
    Utilizza field_mask e process_options se configurati.
    """
    if not os.path.exists(file_path):
        messagebox.showerror("Errore File", f"Errore: Il file '{file_path}' non esiste.")
        return

    print(f"\n--- Inizio Processamento ---")
    print(f"Documento: {file_path}")
    print(f"Processore: {PROCESSOR_PATH}")
    if FIELD_MASK:
        print(f"Field Mask applicato: {FIELD_MASK}")
    if PROCESS_FIRST_PAGE_ONLY:
        print("Processamento solo della prima pagina.")

    try:
        with open(file_path, "rb") as document_file:
            document_content = document_file.read()
    except IOError as e:
        messagebox.showerror("Errore Lettura File", f"Errore nella lettura del file '{file_path}': {e}")
        return

    raw_document = documentai.RawDocument(content=document_content, mime_type="application/pdf")

    # --- Configurazione delle opzioni di processamento (process_options) ---
    process_options = None
    if PROCESS_FIRST_PAGE_ONLY:
        process_options = documentai.ProcessOptions(
            individual_page_selector=documentai.ProcessOptions.IndividualPageSelector(
                pages=[1] # Processa solo la pagina 1 (indice 0 è la prima pagina)
            )
        )

    # Crea la richiesta di processamento, includendo field_mask e process_options se definiti
    request = documentai.ProcessRequest(
        name=PROCESSOR_PATH,
        raw_document=raw_document,
        field_mask=FIELD_MASK, # Passa il field_mask se impostato
        process_options=process_options, # Passa le opzioni di processamento se impostate
    )

    try:
        print("Invio richiesta a Google Document AI...")
        result = client.process_document(request=request)
        document_proto = result.document

#KDFGKJDKG
        # Salva il JSON su file invece di stamparlo
        json_output = documentai.Document.to_json(document_proto)
        output_filename = f"{os.path.splitext(os.path.basename(file_path))[0]}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path = os.path.join(os.path.dirname(file_path), output_filename)
        
        with open(output_path, 'w', encoding='utf-8') as json_file:
            json.dump(json.loads(json_output), json_file, indent=2, ensure_ascii=False)

        # DFJDFJHDH
        # FBechelli in progress
        # Trasformazione
        #dati_trasformati = rimappa_json(document_proto)
#
#       # # Salvataggio in un nuovo file
        #
        #out2_filename = f"{os.path.splitext(os.path.basename(file_path))[0]}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.out.json"
        #out2_path = os.path.join(os.path.dirname(file_path), out2_filename)
#
        #with open(out2_path, "w", encoding="utf-8") as f:
        #    json.dump(dati_trasformati, f, ensure_ascii=False, indent=2)
        
        print(f"\n--- JSON salvato in: {output_path} ---")


        # FBechelli - Per print a terminale
        #print("\n--- Testo estratto (OCR) ---")
        #if document_proto.text:
        #    print(document_proto.text)
        #else:
        #    print("Nessun testo grezzo estratto. Il processore potrebbe non essere un OCR o il documento è vuoto.")
#
        #if document_proto.entities:
        #    print("\n--- Entità estratte ---")
        #    for entity in document_proto.entities:
        #        print(f" '{entity}'")
        #        if entity.properties:
        #            print("    Proprietà:")
        #            for prop in entity.properties:
        #                print(f"      - {prop}")
        #elif document_proto.pages:
        #    for i, page in enumerate(document_proto.pages):
        #        if page.form_fields:
        #            print(f"\n--- Campi modulo estratti (Pagina {i+1}) ---")
        #            for field in page.form_fields:
        #                field_name = field.field_name.text if field.field_name else "N/A"
        #                field_value = field.field_value.text if field.field_value else "N/A"
        #                print(f"  Campo: '{field_name}', Valore: '{field_value}', Confidence: {field.field_value.confidence:.2f}")
#
        #        if page.tables:
        #            print(f"\n--- Tabelle estratte (Pagina {i+1}) ---")
        #            for j, table in enumerate(page.tables):
        #                print(f"  Tabella {j+1}:")
        #                for row_index, row in enumerate(table.header_rows):
        #                    header_values = [cell.text for cell in row.cells]
        #                    print(f"    Header {row_index+1}: {header_values}")
        #                for row_index, row in enumerate(table.body_rows):
        #                    row_values = [cell.text for cell in row.cells]
        #                    print(f"    Riga {row_index+1}: {row_values}")
#
        if not document_proto.entities and not any(page.form_fields or page.tables for page in document_proto.pages):
            print("\nNessuna entità, campo modulo o tabella estratta (il processore potrebbe essere solo OCR o i dati non sono stati riconosciuti).")
        
        messagebox.showinfo("Processamento Completato", f"Il documento è stato processato con successo! JSON salvato in: {output_path}")

    except Exception as e:
        error_message = f"Si è verificato un errore durante il processamento Document AI: {e}\n\n" \
                        "Causa comune:\n" \
                        "  - Problemi di autenticazione: Assicurati che le credenziali siano corrette e che l'account abbia i permessi.\n" \
                        "  - Processore non trovato/non valido: Controlla gli ID e la regione nel tuo .env.\n" \
                        "  - Errore di rete/server Google Cloud: Riprova più tardi."
        print(f"\n{error_message}")
        messagebox.showerror("Errore Document AI", error_message)

    print("\n--- Fine Processamento ---")



# FINE DEFINIZIONE FUNZIONI

# Punto di ingresso dello script
if __name__ == "__main__":
    # Inizializza un'istanza Tkinter ma la nasconde per non mostrare una finestra vuota
    root = tk.Tk()
    root.withdraw() 

    # Se un percorso è passato come argomento da riga di comando, usalo
    if len(sys.argv) > 1:
        pdf_file_path = sys.argv[1]
        process_document(pdf_file_path)
    else:
        # Altrimenti, apri il dialogo di selezione file
        messagebox.showinfo("Seleziona File PDF", "Seleziona il file PDF (DDT o Ordine) da processare.")
        file_path = filedialog.askopenfilename(
            title="Seleziona File PDF per Document AI",
            filetypes=[("PDF files", "*.pdf")]
        )
        if file_path: # Se l'utente ha selezionato un file
            process_document(file_path)
        else:
            messagebox.showinfo("Selezione Annullata", "Nessun file selezionato. Operazione annullata.")
            sys.exit(0)