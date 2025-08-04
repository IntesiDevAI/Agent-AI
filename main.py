# main.py
import argparse
import uvicorn
from api import app
from db_data import record_data
from dotenv import load_dotenv
import logging
import os

load_dotenv()
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_file", nargs="?", help="Percorso del file PDF da registrare")
    args = parser.parse_args()

    if args.pdf_file:
        try:
            recid, status = record_data(args.pdf_file)
            print({"status": "success", "recid": recid, "db_status": status})
        except Exception as e:
            logging.error(f"Errore CLI: {e}")
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)
