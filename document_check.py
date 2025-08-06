from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
import httpx
import os
from dotenv import load_dotenv
import logging

router = APIRouter()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
CLEVERP_BASE_URL = os.getenv("CLEVERP_BASE_URL")

class Riga(BaseModel):
    numero_riga: str
    codice_articolo: str
    descrizione: str
    quantità: int
    prezzo: float

class DocumentoData(BaseModel):
    cliente: str
    numero_documento: str
    data_documento: str
    rif: Optional[str]
    righe: List[Riga]

class DocumentoInput(BaseModel):
    model: str
    provider: str
    data: DocumentoData

class DocumentoOutput(BaseModel):
    cliente: bool
    codice_cliente: Optional[str]
    articoli_trovati: List[str]
    articoli_mancanti: List[str]

async def cerca_cliente(description: str) -> Optional[str]:
    url = f"{CLEVERP_BASE_URL}/Customer/GetManagedData"
    payload = {
        "Page": {"Index": 0, "Size": 1},
        "RequireTotalCount": False,
        "Select": ["Code"],
        "Where": f"Description like '%{description}%'"
    }

    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(url, json=payload)
            res.raise_for_status()
            data = res.json().get("data", [])
            if data:
                return data[0].get("Code")
        except Exception as e:
            logger.error(f"Errore cliente: {e}")
    return None

async def articoli_esistenti(codici: List[str]) -> List[str]:
    url = f"{CLEVERP_BASE_URL}/Part/GetManagedData"
    trovati = []

    async with httpx.AsyncClient() as client:
        for code in codici:
            payload = {
                "Page": {"Index": 0, "Size": 1},
                "RequireTotalCount": False,
                "Select": ["Code"],
                "Where": f"Code = '{code}'"
            }
            try:
                res = await client.post(url, json=payload)
                res.raise_for_status()
                data = res.json().get("data", [])
                if data:
                    trovati.append(code)
            except Exception as e:
                logger.error(f"Errore articolo {code}: {e}")
    return trovati

@router.post("/verifica-documento", response_model=DocumentoOutput)
async def verifica_documento(doc: DocumentoInput):
    codice_cliente = await cerca_cliente(doc.data.cliente)
    cliente_trovato = codice_cliente is not None

    codici_articolo = list({r.codice_articolo for r in doc.data.righe})
    articoli_trovati = await articoli_esistenti(codici_articolo)
    articoli_mancanti = list(set(codici_articolo) - set(articoli_trovati))

    return DocumentoOutput(
        cliente=cliente_trovato,
        codice_cliente=codice_cliente,
        articoli_trovati=articoli_trovati,
        articoli_mancanti=articoli_mancanti
    )
