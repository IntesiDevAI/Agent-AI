#!/usr/bin/env python3
"""
glocal_ai_confronto.py
======================

Questo script fornisce un’interfaccia da linea di comando per
confrontare l’estrazione dei dati da un documento PDF utilizzando due
approcci diversi:

* **Google Document AI** – tramite le API di Google Cloud.  Lo
  script chiama direttamente il servizio Document AI usando le
  credenziali e gli identificativi definiti nelle variabili
  d’ambiente `GOOGLE_CLOUD_PROJECT_ID`, `DOCUMENT_AI_LOCATION` e
  `DOCUMENT_AI_PROCESSOR_ID`.  Per la rimappatura del risultato
  complesso restituito da Document AI in una struttura più semplice
  viene implementata una funzione locale che replica la logica
  presente nel modulo ``gdocai.rimappa_json``.

* **ChatGPT/LLM** – tramite l’OCR locale e un modello di grande
  linguaggio (LLM).  Lo script utilizza le funzioni esistenti
  ``extract_text_from_pdf`` (da ``pdf_reader.py``) e
  ``extract_data_from_text`` (da ``llm_agent.py``) per ottenere un
  testo OCR dal PDF e quindi far estrarre i campi desiderati dal
  modello LLM.  Il modello e il provider possono essere
  specificati tramite opzioni della CLI.

L’utente può scegliere quale metodo utilizzare (``google``,
``chatgpt`` oppure ``both``) ed il risultato viene stampato come
oggetto JSON.  Questo consente di confrontare rapidamente la qualità
dei due approcci sulla stessa fonte.

Esempio d’uso:

.. code-block:: bash

    python glocal_ai_confronto.py ~/documenti/ddt.pdf --method both

Requisiti:

* Per usare Document AI occorre impostare le variabili d’ambiente
  ``GOOGLE_CLOUD_PROJECT_ID`` e ``DOCUMENT_AI_PROCESSOR_ID`` e avere
  configurato le credenziali applicative Google (tramite
  ``GOOGLE_APPLICATION_CREDENTIALS`` o un file JSON).  L’endpoint
  predefinito usa la regione ``eu`` ma può essere modificato tramite
  ``DOCUMENT_AI_LOCATION``.
* Per usare ChatGPT occorre una chiave API valida per il provider
  scelto (OpenAI oppure OpenRouter) e definita nelle variabili
  d’ambiente corrispondenti.  La funzione ``extract_data_from_text``
  definita in ``llm_agent.py`` utilizza le librerie ``langchain`` e
  ``ChatOpenAI``.
"""

import argparse
import json
import os
from typing import Dict, Any, List, Sequence, Optional, Iterable

# Carica automaticamente le variabili dal file .env se presente.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    # Se python-dotenv non è installato o il file .env non è presente,
    # semplicemente ignoriamo il caricamento. Gli utenti possono
    # impostare le variabili d'ambiente manualmente.
    pass


def _getattr(obj: Any, attr: str, default: Optional[Any] = None) -> Any:
    """Recupera un attributo da un oggetto oppure una chiave da un dizionario.

    Se ``obj`` è ``None``, restituisce ``default``.  Se ``obj`` è un
    dizionario, usa ``obj.get(attr, default)``, altrimenti usa
    ``getattr(obj, attr, default)``.
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _get_entities(document: Any) -> Sequence[Any]:
    """Restituisce la sequenza di entità dal documento."""
    return _getattr(document, "entities", []) or []


def _get_pages(document: Any) -> Sequence[Any]:
    """Restituisce la sequenza di pagine dal documento."""
    return _getattr(document, "pages", []) or []


def _get_entity_type(entity: Any) -> str:
    """Restituisce il tipo di entità in minuscolo."""
    return (_getattr(entity, "type_", None) or _getattr(entity, "type", "")).lower()


def _get_entity_mention(entity: Any) -> str:
    """Restituisce il testo associato a un'entità."""
    return (
        _getattr(entity, "mention_text", None)
        or _getattr(entity, "mentionText", "")
        or ""
    ).strip()


def _get_entity_properties(entity: Any) -> Sequence[Any]:
    """Restituisce la sequenza di proprietà di un'entità."""
    return _getattr(entity, "properties", []) or []


def _get_property_type(prop: Any) -> str:
    """Restituisce il tipo di una proprietà in minuscolo."""
    return (_getattr(prop, "type_", None) or _getattr(prop, "type", "")).lower()


def _get_property_mention(prop: Any) -> str:
    """Restituisce il testo associato a una proprietà."""
    return (
        _getattr(prop, "mention_text", None)
        or _getattr(prop, "mentionText", "")
        or ""
    ).strip()


def _get_document_text(document: Any) -> str:
    """Restituisce il testo completo del documento."""
    return _getattr(document, "text", "") or ""


def _get_tables(page: Any) -> Sequence[Any]:
    """Restituisce la sequenza di tabelle presenti in una pagina."""
    return _getattr(page, "tables", []) or []


def _get_header_rows(table: Any) -> Sequence[Any]:
    """Restituisce le righe di intestazione della tabella."""
    return _getattr(table, "header_rows", None) or _getattr(table, "headerRows", []) or []


def _get_body_rows(table: Any) -> Sequence[Any]:
    """Restituisce le righe del corpo della tabella."""
    return _getattr(table, "body_rows", None) or _getattr(table, "bodyRows", []) or []


def _get_cells(row: Any) -> Sequence[Any]:
    """Restituisce le celle di una riga."""
    return _getattr(row, "cells", []) or []


def _get_layout(cell: Any) -> Any:
    """Restituisce il layout di una cella."""
    return _getattr(cell, "layout", {}) or {}


def _get_text_anchor(layout: Any) -> Any:
    """Restituisce l'ancora di testo di un layout."""
    return _getattr(layout, "text_anchor", None) or _getattr(layout, "textAnchor", {}) or {}


def _get_text_segments(anchor: Any) -> Sequence[Any]:
    """Restituisce i segmenti di testo dell'ancora."""
    return _getattr(anchor, "text_segments", None) or _getattr(anchor, "textSegments", []) or []


def _extract_text_from_segments(segments: Iterable[Any], full_text: str) -> str:
    """Compone il testo concatenando tutti i segmenti indicati."""
    text = ""
    for seg in segments:
        start = _getattr(seg, "start_index", None)
        if start is None:
            start = _getattr(seg, "startIndex", 0)
        end = _getattr(seg, "end_index", None)
        if end is None:
            end = _getattr(seg, "endIndex", 0)
        try:
            start = int(start)
            end = int(end)
        except Exception:
            continue
        text += full_text[start:end]
    return text.strip()


def _cell_text(cell: Any, full_text: str) -> str:
    """Estrae il testo da una cella di tabella."""
    layout = _get_layout(cell)
    anchor = _get_text_anchor(layout)
    segments = _get_text_segments(anchor)
    return _extract_text_from_segments(segments, full_text) if segments else ""


def _parse_number(value_str: Optional[str]) -> Optional[float]:
    """Converte una stringa in float, gestendo il formato italiano (virgola).

    Se ``value_str`` è ``None`` o non è convertibile in numero, restituisce
    ``None``.
    """
    if not value_str:
        return None
    try:
        cleaned = value_str.replace(".", "").replace(",", ".")
        return float(cleaned)
    except Exception:
        return None


def rimappa_document_ai(document_proto: Any) -> Dict[str, Any]:
    """Rimappa l'output di Document AI in una struttura semplificata.

    Questa funzione replica la logica presente in ``gdocai.rimappa_json``
    evitando di importare il modulo ``gdocai`` (che potrebbe richiedere
    ``tkinter``) e utilizzando invece le funzioni helper definite
    localmente.  Restituisce un dizionario con i campi:
    ``fornitore``, ``numero_documento``, ``data_documento`` e un array
    ``riga`` di righe di dettaglio (progressivo_riga, riferimento,
    codice_articolo, descrizione, quantità, prezzo).
    """
    risultato: Dict[str, Any] = {
        "fornitore": "",
        "numero_documento": "",
        "data_documento": "",
        "riga": [],
    }

    # Testo completo usato per estrarre il contenuto delle celle
    full_text = _get_document_text(document_proto)

    # 1) Campi principali dal blocco entità
    for ent in _get_entities(document_proto):
        etype = _get_entity_type(ent).lower()
        evalue = _get_entity_mention(ent)
        if "fornitore" in etype:
            risultato["fornitore"] = evalue
        elif "numero" in etype:
            risultato["numero_documento"] = evalue
        elif "data" in etype:
            risultato["data_documento"] = evalue

    # 2) Costruisci l'elenco di righe di tabella con codice, quantità e prezzo unitario
    prod_rows: List[Dict[str, Any]] = []
    for page in _get_pages(document_proto):
        for table in _get_tables(page):
            header_rows = _get_header_rows(table)
            if not header_rows:
                continue
            first_header_row = header_rows[0]
            header_cells = _get_cells(first_header_row)
            header = [_cell_text(cell, full_text).lower() for cell in header_cells]

            if "codice articolo" not in header:
                continue
            idx_cod = header.index("codice articolo")
            idx_quant = header.index("quantita'") if "quantita'" in header else None
            idx_price_unit = header.index("prezzo unitario") if "prezzo unitario" in header else None
            idx_price_tot = header.index("prezzo totale") if "prezzo totale" in header else None
            if idx_quant is None:
                continue

            for body_row in _get_body_rows(table):
                cells = _get_cells(body_row)
                if idx_cod >= len(cells) or idx_quant >= len(cells):
                    continue
                code = _cell_text(cells[idx_cod], full_text)
                quant_str = _cell_text(cells[idx_quant], full_text)
                qty = _parse_number(quant_str)
                if code and qty is not None:
                    price_unit = None
                    price_tot = None
                    if idx_price_unit is not None and idx_price_unit < len(cells):
                        price_unit = _parse_number(_cell_text(cells[idx_price_unit], full_text))
                    if idx_price_tot is not None and idx_price_tot < len(cells):
                        price_tot = _parse_number(_cell_text(cells[idx_price_tot], full_text))
                    if price_unit is None and price_tot is not None and qty != 0:
                        price_unit = price_tot / qty
                    prod_rows.append({
                        "codice_articolo": code,
                        "quantita": qty,
                        "prezzo": price_unit,
                    })

    # mappa codice → primo prezzo disponibile
    price_map: Dict[str, float] = {}
    for row in prod_rows:
        if row["prezzo"] is not None and row["codice_articolo"] not in price_map:
            price_map[row["codice_articolo"]] = row["prezzo"]
    prod_remaining = prod_rows.copy()

    def match_price(code: str, qty: Optional[float]) -> Optional[float]:
        if not code:
            return None
        if qty is not None:
            for i, row in enumerate(prod_remaining):
                if row["codice_articolo"] == code and abs(row["quantita"] - qty) < 1e-6:
                    p = row["prezzo"]
                    prod_remaining.pop(i)
                    return p
        for i, row in enumerate(prod_remaining):
            if row["codice_articolo"] == code:
                p = row["prezzo"]
                prod_remaining.pop(i)
                return p
        return None

    # 3) crea la lista delle righe dalle entità di tipo "riga"
    for ent in _get_entities(document_proto):
        if _get_entity_type(ent).lower() != "riga":
            continue
        props: Dict[str, str] = {}
        for prop in _get_entity_properties(ent):
            props[_get_property_type(prop)] = _get_property_mention(prop)
        code = props.get("codice_articolo", "")
        qty_str = props.get("quantita") or props.get("quantità")
        qty = _parse_number(qty_str) if qty_str else None
        price = match_price(code, qty)
        if price is None and code in price_map:
            price = price_map[code]
        if price is None:
            price = 0.0
        risultato["riga"].append({
            "progressivo_riga": str(len(risultato["riga"]) + 1),
            "riferimento": props.get("riferimento", ""),
            "codice_articolo": code,
            "descrizione": props.get("descrizione", ""),
            "quantità": qty if qty is not None else 0.0,
            "prezzo": price,
        })

    return risultato


def extract_with_google_document_ai(file_path: str) -> Dict[str, Any]:
    """Esegue l’estrazione tramite Google Document AI su un file PDF.

    Per funzionare è necessario impostare le variabili d’ambiente
    ``GOOGLE_CLOUD_PROJECT_ID`` (ID del progetto GCP),
    ``DOCUMENT_AI_PROCESSOR_ID`` (ID numerico del processore) e
    facoltativamente ``DOCUMENT_AI_LOCATION`` (la regione, default
    ``eu``), ``DOCUMENT_AI_FIELD_MASK`` e
    ``DOCUMENT_AI_PROCESS_FIRST_PAGE_ONLY``.  Inoltre, devono essere
    presenti le credenziali di servizio per accedere a Document AI,
    tipicamente tramite la variabile ``GOOGLE_APPLICATION_CREDENTIALS``.

    Restituisce un dizionario con la struttura semplificata definita
    da ``rimappa_document_ai``.
    """
    try:
        from google.cloud import documentai_v1 as documentai
        from google.api_core.client_options import ClientOptions
    except ImportError as e:
        raise RuntimeError(
            "Il pacchetto google-cloud-documentai non è installato. "
            "Per utilizzare Document AI installa 'google-cloud-documentai'."
        ) from e

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
    location = os.getenv("DOCUMENT_AI_LOCATION", "eu")
    processor_id = os.getenv("DOCUMENT_AI_PROCESSOR_ID")
    field_mask = os.getenv("DOCUMENT_AI_FIELD_MASK", None)
    process_first_page_only = os.getenv("DOCUMENT_AI_PROCESS_FIRST_PAGE_ONLY", "0").lower() == "1"

    if not project_id or not processor_id:
        raise RuntimeError(
            "Per usare Google Document AI devi definire le variabili "
            "d'ambiente GOOGLE_CLOUD_PROJECT_ID e DOCUMENT_AI_PROCESSOR_ID."
        )

    processor_path = f"projects/{project_id}/locations/{location}/processors/{processor_id}"
    client_options = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    client = documentai.DocumentProcessorServiceClient(client_options=client_options)

    # Leggi il PDF
    with open(file_path, "rb") as document_file:
        document_content = document_file.read()
    raw_document = documentai.RawDocument(content=document_content, mime_type="application/pdf")

    process_options = None
    if process_first_page_only:
        process_options = documentai.ProcessOptions(
            individual_page_selector=documentai.ProcessOptions.IndividualPageSelector(pages=[1])
        )

    request = documentai.ProcessRequest(
        name=processor_path,
        raw_document=raw_document,
        field_mask=field_mask,
        process_options=process_options,
    )

    result = client.process_document(request=request)
    document_proto = result.document
    return rimappa_document_ai(document_proto)


def extract_with_chatgpt(file_path: str, model: str = "gpt-3.5-turbo", provider: str = "openai") -> Dict[str, Any]:
    """Esegue l’estrazione tramite OCR + modello LLM su un file PDF.

    Questo metodo esegue internamente l’OCR tramite ``pdf_reader.extract_text_from_pdf`` e
    invoca un modello di grande linguaggio (LLM) tramite la libreria
    ``langchain`` con un prompt specifico.  Il risultato generato dal modello
    viene decodificato in JSON.  In caso di errori di parsing vengono
    applicati tentativi di recupero e viene sollevata un’eccezione con
    informazioni utili.

    :param file_path: percorso del file PDF
    :param model: nome del modello LLM (es. "gpt-3.5-turbo", "gpt-4")
    :param provider: provider del modello ("openai" o "openrouter")
    :return: dizionario con la struttura dei dati estratti
    """
    # Effettua l'OCR sul documento
    try:
        from pdf_reader import extract_text_from_pdf
    except Exception as e:
        raise RuntimeError(
            "Impossibile importare pdf_reader.extract_text_from_pdf. "
            "Assicurati che le dipendenze per l'OCR siano installate."
        ) from e
    text = extract_text_from_pdf(file_path)

    # Importa i componenti necessari per il prompt e l'LLM
    from langchain.chains import LLMChain
    from langchain.prompts import PromptTemplate
    from langchain_community.chat_models import ChatOpenAI
    import re

    # Prompt per l'estrazione dei dati, identico a quello usato in llm_agent.py
    prompt = PromptTemplate(
        input_variables=["input"],
        template="""
Agisci come un estrattore di dati altamente preciso da Documenti di Trasporto (data).
Riceverai testo estratto da un PDF (anche via OCR).
Aggiungi ad ogni riga estratta il progressivo_riga partendo da 1.
Il campo riferimento può essere indicato: riga per riga, oppure riportato all'inizio di un gruppo di articoli ed è valido per ognuno di essi finché non viene specificato un nuovo riferimento.
Il campo codice_articolo potrebbe non essere presente in tutte le righe. Se assente o non leggibile, imposta il valore a null.
La quantità potrebbe non essere presente in tutte le righe. Se assente o non leggibile, imposta il valore a null.
Se un campo non è leggibile o assente, imposta il valore a null.

Estrai i seguenti campi:

fornitore
numero_documento
data_documento
riga (progressivo_riga, riferimento , codice_articolo, descrizione, quantità, prezzo)

Se un campo non è leggibile o assente, imposta il valore a null.

Restituisci un JSON strutturato con questa forma:
{{
  "fornitore": "...",
  "numero_documento": "...",
  "data_documento": "...",
  "riga": [
    {{
      "progressivo_riga": "...",
      "riferimento": "...",
      "codice_articolo": "...",
      "descrizione": "...",
      "quantità": ...,
      "prezzo": ...
    }}
  ]
}}
Non generare spiegazioni, restituisci solo il JSON.

Testo di input:
{input}
        """,
    )

    # Selezione del provider e configurazione del modello
    if provider == "openai":
        try:
            llm = ChatOpenAI(
                model_name=model,
                temperature=0,
                model_kwargs={"response_format": {"type": "json_object"}},
            )
        except TypeError:
            llm = ChatOpenAI(model_name=model, temperature=0)
    elif provider == "openrouter":
        try:
            llm = ChatOpenAI(
                model_name=model,
                temperature=0,
                openai_api_base="https://openrouter.ai/api/v1",
                openai_api_key=os.getenv("OPENROUTER_API_KEY"),
                model_kwargs={"response_format": {"type": "json_object"}},
            )
        except TypeError:
            llm = ChatOpenAI(
                model_name=model,
                temperature=0,
                openai_api_base="https://openrouter.ai/api/v1",
                openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            )
    else:
        raise ValueError(f"Provider '{provider}' non supportato al momento.")

    chain = LLMChain(llm=llm, prompt=prompt)
    response = chain.run({"input": text})

    # Prova a decodificare direttamente come JSON
    try:
        return json.loads(response)
    except Exception:
        # Cerca la prima struttura JSON nel testo
        match = re.search(r"\{.*\}", response, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        raise RuntimeError(
            "Errore nel parsing del JSON generato dal modello. "
            "Risposta ricevuta:\n" + response
        )


def main() -> None:
    """Punto di ingresso dell’applicazione da CLI."""
    parser = argparse.ArgumentParser(
        description=(
            "Confronta l'estrazione dei dati da un PDF usando Google "
            "Document AI e/o ChatGPT/LLM."
        )
    )
    parser.add_argument(
        "pdf_path",
        help="Percorso completo del file PDF da processare."
    )
    parser.add_argument(
        "--method",
        choices=["google", "chatgpt", "both"],
        default="both",
        help=(
            "Metodo di estrazione da utilizzare: "
            "'google' per Document AI, 'chatgpt' per LLM oppure 'both' per entrambi."
        ),
    )
    parser.add_argument(
        "--model",
        default="gpt-3.5-turbo",
        help="Nome del modello LLM da usare per ChatGPT (es. gpt-4, gpt-3.5-turbo).",
    )
    parser.add_argument(
        "--provider",
        default="openai",
        help="Provider LLM (openai oppure openrouter)."
    )

    args = parser.parse_args()

    pdf_path = args.pdf_path
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"Il file specificato non esiste: {pdf_path}")

    results: Dict[str, Any] = {}

    # Esecuzione del metodo Google Document AI
    if args.method in ("google", "both"):
        try:
            print("[Info] Avvio estrazione tramite Google Document AI…")
            results["google"] = extract_with_google_document_ai(pdf_path)
        except Exception as e:
            results["google_error"] = str(e)

    # Esecuzione del metodo ChatGPT
    if args.method in ("chatgpt", "both"):
        try:
            print("[Info] Avvio estrazione tramite ChatGPT/LLM…")
            results["chatgpt"] = extract_with_chatgpt(pdf_path, model=args.model, provider=args.provider)
        except Exception as e:
            results["chatgpt_error"] = str(e)

    # Stampa il risultato JSON per confronto
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()