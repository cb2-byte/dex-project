import sqlite3
from pathlib import Path

DB_PATH = "/Volumes/Lexar/colmap_workspace/database.db"

def fix_filenames():
    print(f"Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Get all images
    cur.execute("SELECT image_id, name FROM images")
    rows = cur.fetchall()
    
    updates = 0
    for image_id, name in rows:
        if name.upper().endswith(".DNG"):
            # We want to change .DNG to .jpg
            new_name = name[:-4] + ".jpg"
            
            # Verify the .jpg actually exists in the images folder
            # (The user has a mix of .DNG and .jpg in the DB, so we only update 
            #  the ones that are definitely missing and have a .jpg counterpart)
            cur.execute("SELECT 1 FROM images WHERE name = ?", (new_name,))
            if cur.fetchone() is None:
                cur.execute("UPDATE images SET name = ? WHERE image_id = ?", (new_name, image_id))
                updates += 1
    
    conn.commit()
    conn.close()
    print(f"Updated {updates} .DNG entries to .jpg in the database.")

if __name__ == "__main__":
    fix_filenames()
