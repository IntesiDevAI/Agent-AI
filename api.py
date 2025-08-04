import logging
import os
import tempfile

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel

from document_check import router as document_router
from pdf_reader import extract_text_from_pdf
from llm_agent import extract_data_from_text

from db_data import record_data, get_status_by_recid, update_status, save_extraction_results
from data_utils import extract_data_from_file

app = FastAPI(
    title="Cleverp Chatbot API",
    version="1.0",
    description="API per estrazione dati da data e interazione chatbot da Cleverp"
)

app.include_router(document_router)

# Schema di sicurezza
security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def process_pdf_background(tmp_path: str, recid: int, model: str, provider: str):
    try:
        result = extract_data_from_file(tmp_path, model, provider)

        # Salvataggio nel DB (assicurati che questa funzione sia presente nel tuo db_data.py)
        save_extraction_results(recid, result["text"], result["data"])
        update_status(recid, 4)  # Successo

    except Exception as e:
        logging.error(f"Errore nel background task per RecId {recid}: {e}")
        update_status(recid, 99)  # Errore

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)




@app.post(
    "/upload-pdf",
    summary="Upload Pdf",
    description="""
Carica un documento DDT (PDF o immagine).  
Il file viene registrato nel database e analizzato **in background** usando OCR + LLM.

📌 Restituisce subito:
- `recid`: ID univoco nel DB
- `db_status`: stato attuale (es. "In elaborazione")

ℹ️ Il risultato elaborato può essere recuperato più tardi con `/status/{recid}`.
"""
)
async def upload_pdf(
                        #background_tasks: BackgroundTasks,
                        file: UploadFile = File(...)
                        #, model: str = "gpt-3.5-turbo", provider: str = "openai"
                        ):
    if not file.filename.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")):
        raise HTTPException(status_code=400, detail="Formato non supportato. Usa PDF o immagine.")
    
    tmp_path = ""
    try:
        # 1. Salva il file temporaneamente
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        # 2. Registra nel database
        recid, status = record_data(tmp_path)


        model: str = "gpt-3.5-turbo" 
        provider: str = "openai"
        # background_tasks.add_task(process_pdf_background, tmp_path, recid, model, provider)

        
        return {
            "status": "success",
            "recid": recid,
            "db_status": status
        }

    except Exception as e:
        logging.error(f"Errore API: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        pass  # Il file verrà rimosso nel background task



@app.get(
    "/status/{recid}",
    summary="Get Status",
    description="""
Controlla lo stato di elaborazione del documento con `RecId`.

📌 Possibili stati:
- "In elaborazione"
- "Elaborato"
- "Errore"
- "Non Trovato"

Utile per verificare se l'elaborazione asincrona è completata.
"""
)
def get_status(recid: int):
    try:
        status = get_status_by_recid(recid)
        if status is None:
            raise HTTPException(status_code=404, detail="RecId non trovato")
        return {"recid": recid, "status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Modello per /api/v1/run
class ChatRequest(BaseModel):
    text: str



@app.post(
    "/extract-data",
    summary="Extract data",
    description="""
Elabora un file data in tempo reale (**OCR + LLM**) e restituisce immediatamente il risultato.

⚠️ Non salva nulla nel database.

Utile per test o casi in cui non serve storicizzare i dati.
"""
)
async def extract_data(file: UploadFile = File(...), model: str = "gpt-3.5-turbo", provider: str = "openai"):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(await file.read())
            temp_path = temp_file.name

        result = extract_data_from_file(temp_path, model, provider)

        os.unlink(temp_path)
        return result

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'elaborazione: {str(e)}")