from pdf_reader import extract_text_from_pdf
from llm_agent import extract_data_from_text

def extract_data_from_file(file_path: str, model: str = "gpt-3.5-turbo", provider: str = "openai"):
    """
    Esegue OCR e parsing LLM su un file data.

    :param file_path: Percorso del file PDF
    :param model: Nome del modello LLM
    :param provider: Provider (es. OpenAI)
    :return: dict con testo OCR, dati estratti, modello e provider
    """
    try:
        text = extract_text_from_pdf(file_path)
        data = extract_data_from_text(text, model_name=model, provider=provider)
        return {
            "text": text,
            "data": data,
            "model": model,
            "provider": provider
        }
    except Exception as e:
        raise RuntimeError(f"Errore durante l'elaborazione del file data: {e}")
