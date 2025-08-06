# main.py
import argparse
import uvicorn
import os
import time
from api import app
from db_data import record_data, get_status_by_recid, update_status, save_extraction_results
from data_utils import extract_data_from_file
from dotenv import load_dotenv
import logging
import os

load_dotenv()
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Interfaccia CLI per elaborazione documenti")
    
    # Existing arguments for direct PDF processing
    parser.add_argument("pdf_path", nargs="?", help="Percorso completo del file PDF")
    parser.add_argument("original_filename", nargs="?", help="Nome originale del file PDF")
    parser.add_argument("user_prompt", nargs="?", help="Prompt da usare per l'elaborazione")
    
    # New pipeline execution flags
    parser.add_argument("--pipeline-file", help="Esegui pipeline con file")
    parser.add_argument("--pipeline-prompt", help="Prompt per pipeline")
    
    args = parser.parse_args()
    
    if args.pipeline_file or args.pipeline_prompt:
        # Pipeline execution mode
        from db_data import record_data, update_status, save_extraction_results
        from data_utils import extract_data_from_file
        
        try:
            recid, status = record_data(
                args.pipeline_file,
                os.path.basename(args.pipeline_file) if args.pipeline_file else None,
                args.pipeline_prompt
            )
            
            # Process synchronously for CLI
            update_status(recid, 2)
            if args.pipeline_file:
                result = extract_data_from_file(args.pipeline_file, "gpt-3.5-turbo", "openai")
                save_extraction_results(recid, result["text"], result["data"])
            update_status(recid, 4)
            
            print(f"Pipeline completata - RecID: {recid}")
            print({"status": "success", "recid": recid, "db_status": status})
            
        except Exception as e:
            logging.error(f"Errore pipeline: {e}")
    
    elif args.pdf_path:
        try:
            # Existing PDF processing
                recid, status = record_data(args.pdf_path, args.original_filename, args.user_prompt)
                print({"status": "success", "recid": recid, "db_status": status})
        except Exception as e:
            logging.error(f"Errore CLI: {e}")
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)
