# llm_agent.py

import os
import json
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
from langchain_community.chat_models import ChatOpenAI

load_dotenv()  # Carica variabili da .env

def extract_data_from_text(text: str, model_name: str = "gpt-3.5-turbo", provider: str = "openai") -> dict:
    # Prompt per l'estrazione dei dati da data
    prompt = PromptTemplate(
        input_variables=["input"],
        template="""
Agisci come un estrattore di dati altamente preciso da Documenti di Trasporto (data). Riceverai testo estratto da un PDF (anche via OCR). Estrai i seguenti campi:
- fornitore
- numero_documento
- data_documento
- riferimento_documento_precedente
- righe (numero_riga, codice_articolo, descrizione, quantità, prezzo)

Se un campo non è leggibile o assente, imposta il valore a null.

Restituisci un JSON strutturato con questa forma:
{{
  "fornitore": "...",
  "numero_documento": "...",
  "data_documento": "...",
  "riferimento_documento_precedente": "...",
  "righe": [
    {{
      "numero_riga": "...",
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
"""
    )

    # Scelta del provider LLM
    if provider == "openai":
        llm = ChatOpenAI(
            model_name=model_name,
            temperature=0
        )
    elif provider == "openrouter":
        llm = ChatOpenAI(
            model_name=model_name,
            temperature=0,
            openai_api_base="https://openrouter.ai/api/v1",
            openai_api_key=os.getenv("OPENROUTER_API_KEY")
        )
    else:
        raise ValueError(f"Provider '{provider}' non supportato al momento.")

    # Costruzione della chain e richiesta
    chain = LLMChain(llm=llm, prompt=prompt)
    response = chain.run({"input": text})

    # Parsing del JSON generato
    try:
        return json.loads(response)
    except Exception as e:
        raise RuntimeError(f"Errore nel parsing del JSON generato dal modello: {str(e)}")