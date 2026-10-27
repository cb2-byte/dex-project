import sqlite3
import subprocess
import os
from pathlib import Path

db_path = Path("./colmap_workspace/database.db")
image_dir = Path("./colmap_workspace/images")

if not db_path.exists():
    print(f"Error: Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Ensure the prior columns exist (COLMAP doesn't create them by default in some versions)
try:
    cur.execute("ALTER TABLE images ADD COLUMN prior_tx REAL")
    cur.execute("ALTER TABLE images ADD COLUMN prior_ty REAL")
    cur.execute("ALTER TABLE images ADD COLUMN prior_tz REAL")
    print("Added prior columns to database.")
except sqlite3.OperationalError:
    # Columns already exist
    pass

# Get all images from DB
cur.execute("SELECT image_id, name FROM images")
images = cur.fetchall()

count = 0
for image_id, name in images:
    img_path = image_dir / name
    if not img_path.exists():
        continue

    # Pull GPS with exiftool -n (decimal degrees)
    result = subprocess.run([
        "exiftool", "-GPSLatitude#", "-GPSLongitude#", "-GPSAltitude#", "-n", str(img_path)
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
        # Note: COLMAP usually expects lon, lat, alt for tx, ty, tz
        cur.execute("""
        UPDATE images 
        SET prior_tx=?, prior_ty=?, prior_tz=? 
        WHERE image_id=?
        """, (lon, lat, alt, image_id))
        count += 1

conn.commit()
conn.close()
print(f"GPS injection complete! Processed {count} images with coordinates.")
