from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends, BackgroundTasks, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from pydantic import BaseModel
from starlette.datastructures import FormData

from typing import Optional, Union, Dict, Any
from json import JSONDecodeError
import tempfile
import os
import logging

# ROUTER & LOGIC IMPORTS
from document_check import router as document_router
from pdf_reader import extract_text_from_pdf
from llm_agent import extract_data_from_text
from db_data import (
    record_data,
    get_status_by_recid,
    update_status,
    save_extraction_results
)
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
    allow_credentials=True,
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
        update_status(recid, 97)  # Errore

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
        recid, status = record_data(tmp_path, file.filename)



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
    

from typing import Optional
import os
import tempfile
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException, status
from fastapi.responses import JSONResponse
from db_data import record_data, save_extraction_results, update_status
from data_utils import extract_data_from_file


# Da eliminare prova Danilo
#def _process_pipeline_background_BCK(
#    tmp_path: Optional[str],
#    recid: int,
#    user_prompt: Optional[str],
#    model: str = "gpt-3.5-turbo",
#    provider: str = "openai"
#):
#    """
#    Funzione chiamata in background.
#    Se tmp_path non è None, fa extract_data_from_file e salva i risultati.
#    Altrimenti, si occupa solo di processare il prompt (se rimos so desideri).
#    """
#    try:
#        update_status(recid, 2)  # "In elaborazione"
#        result = None
#
#        if tmp_path:
#            result = extract_data_from_file(tmp_path, model, provider)
#            save_extraction_results(recid, result["text"], result["data"])
#            update_status(recid, 4)  # "Elaborato"
#        else:
#            # Se gestisci LLM solo su prompt, chiamalo qui:
#            # extracted = extract_data_from_text(user_prompt)
#            # save_extraction_results(recid, extracted["text"], extracted["data"])
#            update_status(recid, 4)
#
#    except Exception as e:
#        update_status(recid, 99)  # "Errore"
#        app.logger.error(f"[pipeline-bg] RecId={recid} error: {e}")
#
#    finally:
#        if tmp_path and os.path.exists(tmp_path):
#            os.remove(tmp_path)



from fastapi import Request, Depends, HTTPException
from starlette.datastructures import FormData
from typing import Union
from json import JSONDecodeError
# --- [1] Dependency: decodifica JSON o form-data manualmente ---
async def decode_body(request: Request) -> Union[dict, FormData]:
    ct: str = request.headers.get("content-type", "")
    if ct.startswith("application/json"):
        try:
            return await request.json()
        except JSONDecodeError:
            raise HTTPException(status_code=400, detail="JSON non valido")
    elif ct.startswith("multipart/form-data") or ct.startswith("application/x-www-form-urlencoded"):
        try:
            return await request.form()
        except Exception:
            raise HTTPException(status_code=400, detail="Form-data non valido")
    else:
        raise HTTPException(status_code=400, detail="Content-Type non supportato")

# --- [2] Task eseguito in background (solo se esiste file) ---
def _process_pipeline_background(tmp_path: Optional[str], recid: int, user_prompt: Optional[str]):
    try:
        
        update_status(recid, 2)  # "In elaborazione"

        if tmp_path:
            result = extract_data_from_file(tmp_path, model="gpt-3.5-turbo", provider="openai")
            save_extraction_results(recid, result["text"], result["data"])
        
        update_status(recid, 4)  # "Elaborato"
    except Exception as e:
        update_status(recid, 98)  # "Errore"
        # qui puoi fare log dell'errore se vuoi
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

# --- [3] Endpoint /pipelines: usa decode_body, non definisce file/form nei parametri ---
@app.post("/pipelines")
async def run_pipeline(
    request: Request,
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None, description="File PDF o immagine (opzionale)"),
    user_prompt: Optional[str] = Form(None, description="Testo prompt utente (opzionale)"),
    body: Any = Depends(decode_body),
):
    is_form = isinstance(body, FormData)

    uploaded_file = body.get("file") if is_form else None
    user_prompt_raw = (body.get("user_prompt") or "").strip() if is_form else (body.get("user_prompt") or "").strip()
    user_prompt = user_prompt_raw if user_prompt_raw else None

    if not uploaded_file and not user_prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Devi fornire almeno un file o un user_prompt.")

    tmp_path: Optional[str] = None
    recid: Optional[int] = None

    try:
        if uploaded_file:
            suffix = os.path.splitext(uploaded_file.filename)[1] or ".pdf"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(await uploaded_file.read())
                tmp_path = tmp.name
            recid, db_status = record_data(tmp_path, uploaded_file.filename, user_prompt)
        else:
            recid, db_status = record_data(None, None, user_prompt)


        # Chiamata in background per parsing PDF
        background_tasks.add_task(_process_pipeline_background, tmp_path, recid, user_prompt)
        return {"recid": recid, "db_status": db_status}

    except Exception as e:
        if recid:
            update_status(recid, 99)
        raise HTTPException(status_code=500, detail=str(e))