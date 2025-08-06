import os
import json
import logging
from json_repair import loads as jr_loads, repair_json as jr_repair
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_community.chat_models import ChatOpenAI
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

def extract_data_from_text(text: str, model_name: str = "gpt-3.5-turbo", provider: str = "openai") -> dict:
    prompt = PromptTemplate(
        input_variables=["input"],
        template="""
You are a highly accurate data extractor specialized in Delivery Notes (Documenti di Trasporto - DDT).
You will receive raw text extracted from a PDF file (possibly OCR). Your task is to extract and structure the information in the exact JSON format shown below.

Guidelines:
- Start the "progressivo_riga" from 1 and increment by 1 for each row.
- The field "riferimento" may be indicated per row, or once before a group of items. In such case, assume the same value applies to all subsequent rows until a new one appears.
- The field "codice_articolo" might be missing or illegible: if so, set it to null.
- The field "quantità" might be missing or illegible: if so, set it to null.
- If any other field is unreadable or not present, set it to null.
- All prices must be extracted per row, if available.

If a value is missing or unreadable, you must write null (no quotes). Do NOT use "...", "N/A", "-", or anything else.

Extract the following fields:
- fornitore
- numero_documento
- data_documento
- riga (progressivo_riga, riferimento, codice_articolo, descrizione, quantità, prezzo)

⚠️ Output only valid JSON in this exact structure (with double quotes and nulls where required). Do not include any explanation or additional text.

JSON structure:
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

Text to process:
{input}
"""
    )

    if provider == "openai":
        llm = ChatOpenAI(model_name=model_name, temperature=0)
    elif provider == "openrouter":
        llm = ChatOpenAI(
            model_name=model_name,
            temperature=0,
            openai_api_base="https://openrouter.ai/api/v1",
            openai_api_key=os.getenv("OPENROUTER_API_KEY")
        )
    else:
        raise ValueError(f"Provider '{provider}' non supportato.")

    chain = LLMChain(llm=llm, prompt=prompt)

    try:
        response = chain.run({"input": text})
    except Exception as exc:
        logging.error("LLM error during run(): %s", exc, exc_info=True)
        raise RuntimeError(f"Errore chiamata LLM: {exc}")

    logging.info("LLM raw response:\n%s", response)

    # Primo tentativo di parsing
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        logging.warning("json.loads failed: %s", e)

    # Fallback con json-repair.loads
    try:
        repaired = jr_loads(response)
        logging.info("json-repair.loads succeeded")
        return repaired
    except Exception as e:
        logging.warning("json-repair.loads failed: %s", e)

    # Secondo fallback con json-repair.repair_json
    try:
        fixed = jr_repair(response, return_objects=True)
        logging.info("json-repair.repair_json succeeded")
        return fixed
    except Exception as e:
        logging.error("json-repair.repair_json also failed: %s", e)

    raise RuntimeError("Parsing JSON fallito anche dopo i tentativi di riparazione.")
