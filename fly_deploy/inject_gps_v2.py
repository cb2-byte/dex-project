import sqlite3
import subprocess
import os
from pathlib import Path

# The a-real source of truth for GPS is the original castle folder
RAW_IMAGE_DIR = Path("./gorey_castle")
DB_PATH = Path("./colmap_workspace/database.db")

if not DB_PATH.exists():
    print(f"Error: Database not found at {DB_PATH}")
    exit(1)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Ensure prior columns exist
try:
    cur.execute("ALTER TABLE images ADD COLUMN prior_tx REAL")
    cur.execute("ALTER TABLE images ADD COLUMN prior_ty REAL")
    cur.execute("ALTER TABLE images ADD COLUMN prior_tz REAL")
    print("Added prior columns to database.")
except sqlite3.OperationalError:
    pass

# Get images currently in the COLMAP database
cur.execute("SELECT image_id, name FROM images")
db_images = cur.fetchall()

count = 0
for image_id, name in db_images:
    # Try to find the original .DNG version of this image first
    # (e.g., IMG_3818.jpg -> IMG_3818.DNG)
    stem = Path(name).stem
    original_file = None
    
    # Search for a .DNG or .jpg version in the main castle folder
    for ext in [".DNG", ".jpg", ".jpeg", ".png"]:
        possible_path = RAW_IMAGE_DIR / f"{stem}{ext}"
        if possible_path.exists():
            original_file = possible_path
            break
    
    if not original_file:
        continue

    # Pull GPS from the original high-res file
    result = subprocess.run([
        "exiftool", "-GPSLatitude#", "-GPSLongitude#", "-GPSAltitude#", "-n", str(original_file)
    ], capture_output=True, text=True)

    lat, lon, alt = None, None, 0.0
    for line in result.stdout.splitlines():
        if "GPS Latitude" in line:
            try: lat = float(line.split(":")[-1].strip())
            except: pass
        elif "GPS Longitude" in line:
            try: lon = float(line.split(":")[-1].strip())
            except: pass
        elif "GPS Altitude" in line:
            try: alt = float(line.split(":")[-1].strip())
            except: pass

    if lat is not None and lon is not None:
        cur.execute("""
        UPDATE images 
        SET prior_tx=?, prior_ty=?, prior_tz=? 
        WHERE image_id=?
        """, (lon, lat, alt, image_id))
        count += 1

conn.commit()
conn.close()
print(f"GPS injection complete! Successfully mapped {count} images from RAW/Source files.")
