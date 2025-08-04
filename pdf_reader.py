from pdf2image import convert_from_path
import pytesseract
import os


import platform
import pytesseract

# Imposta il percorso solo su Windows
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_text_from_pdf(pdf_path: str) -> str:
    try:
        # Conversione PDF → Immagini con poppler_path forzato
        images = convert_from_path(pdf_path, dpi=300)
        text = ""
        for img in images:
            text += pytesseract.image_to_string(img)
        return text
    except Exception as e:
        raise RuntimeError(f"Errore durante l'OCR: {str(e)}")