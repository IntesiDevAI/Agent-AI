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
        try:
            # F.Bechelli | Codice proposto da Roo (funziona in locale, da verificare su 249)
            poppler_path = os.environ.get('POPPLER_PATH', r'C:\Program Files\poppler-24.08.0\Library\bin')
            images = convert_from_path(
                pdf_path,
                dpi=300,
                poppler_path=poppler_path
            )
        except Exception as conv_err:
            raise RuntimeError(
                f"PDF conversion failed: {conv_err}\n"
                "1. Verify poppler is installed at:\n"
                r"   C:\Program Files\poppler-24.08.0\Library\bin" + "\n"
                "2. Install via:\n"
                "   - winget: winget install poppler\n"
                "   - chocolatey: choco install poppler\n"
                "   - Manual download: https://github.com/oschwartz10612/poppler-windows/releases"
            )
        text = ""
        for img in images:
            text += pytesseract.image_to_string(img)
        return text
    except Exception as e:
        raise RuntimeError(f"Errore durante l'OCR: {str(e)}")