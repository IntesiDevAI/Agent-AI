# db_data.py
import pyodbc
import os
from datetime import datetime

DB_CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=INTESI\\INTESI2022;"
    "DATABASE=DB-AI;"
    "UID=sa;PWD=Intsupport1!;"
)

def get_db_conn():
    return pyodbc.connect(DB_CONN_STR)

def data(file_path: str, original_filename: str = None):
    with open(file_path, 'rb') as f:
        content = f.read()

    conn = get_db_conn()
    cursor = conn.cursor()
    sql = """
        INSERT INTO Requests (Filename, UploadDate, Data, Status)
        OUTPUT INSERTED.RecId
        VALUES (?, ?, ?, ?)
    """
    filename = original_filename or os.path.basename(file_path)
    now = datetime.utcnow()
    status = 1

    cursor.execute(sql, filename, now, pyodbc.Binary(content), status)
    recid = cursor.fetchone()[0]
    conn.commit()

    cursor.execute("""
        SELECT ISNULL(s.Description, 'Non Trovato')
        FROM Requests r
        LEFT JOIN Status s ON r.Status = s.Id
        WHERE r.RecId = ?
    """, recid)
    status = cursor.fetchone()[0] if cursor.description else "Non Trovato"

    cursor.close()
    conn.close()

    return recid, status

def get_status_by_recid(recid: int):
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT isnull(s.Description,'Non Trovato') FROM Requests r left join Status s on r.Status=s.Id WHERE RecId = ?", recid)
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row[0] if row else None

def update_status(recid: int, status: int):
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE Requests SET Status = ? WHERE RecId = ?", status, recid)
    conn.commit()
    cursor.close()
    conn.close()


def save_extraction_results(recid: int, text: str, data: dict):
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE Requests SET ExtractedText = ?, ExtractedData = ? WHERE RecId = ?",
        text, str(data), recid
    )
    conn.commit()
    cursor.close()
    conn.close()

from typing import Optional

def record_data(
    file_path: Optional[str],
    original_filename: Optional[str],
    user_prompt: Optional[str]
) -> tuple[int, str]:   # Cambia qui
    """
    Inserisce un nuovo record in db. Se 'file_path' è None,
    inserisce solo il prompt; il campo Data/Nome sarà null/empty.
    Restituisce (recid, status_description).
    """
    conn = get_db_conn()
    cursor = conn.cursor()

    now = datetime.utcnow()
    status_code = 1  # STATUS = “Uploaded / In Queue”

    filename = original_filename or ""
    binary_content = None
    if file_path:
        with open(file_path, "rb") as f:
            binary_content = pyodbc.Binary(f.read())

    sql = """
        INSERT INTO Requests
          (Filename, UploadDate, Data, Status, User_Prompt)
        OUTPUT INSERTED.RecId
        VALUES (?, ?, ?, ?, ?)
    """
    cursor.execute(sql, filename, now, binary_content, status_code, user_prompt)
    recid = cursor.fetchone()[0]
    conn.commit()

    cursor.execute("""
        SELECT ISNULL(s.Description, 'Non Trovato')
        FROM Requests r
        LEFT JOIN Status s ON r.Status = s.Id
        WHERE r.RecId = ?
    """, recid)
    status_desc = cursor.fetchone()[0]

    cursor.close()
    conn.close()
    return recid, status_desc


