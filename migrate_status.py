import sqlite3
import os

db_path = 'vakilai.db'
if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(documents)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'status' not in columns:
            cursor.execute('ALTER TABLE documents ADD COLUMN status TEXT DEFAULT "completed"')
            conn.commit()
            print("Successfully added 'status' column.")
        else:
            print("Column 'status' already exists.")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
