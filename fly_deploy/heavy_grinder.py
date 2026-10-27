import os
import subprocess
import sqlite3
import shutil
from pathlib import Path

# --- SETTINGS ---
BASE_DIR = Path("./colmap_workspace")
IMAGE_DIR = BASE_DIR / "images"
DB_PATH = BASE_DIR / "database.db"
SOURCE_DIR = Path("./gorey_castle")

def run_cmd(cmd):
    print(f"Running: {cmd}")
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error: {res.stderr}")
    return res.stdout

def setup_workspace():
    print("Step 1: Cleaning workspace for Heavy Run...")
    if BASE_DIR.exists():
        target = BASE_DIR.resolve()
        for item in target.iterdir():
            item_path = target / item.name
            if item_path.is_dir():
                shutil.rmtree(item_path)
            else:
                item_path.unlink()
    
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    all_jpgs = sorted([f for f in SOURCE_DIR.rglob("*") if f.suffix.lower() in [".jpg", ".jpeg", ".png"]])
    if not all_jpgs:
        print("Error: No images found!")
        return False

    for img in all_jpgs:
        shutil.copy2(img, IMAGE_DIR / img.name)
    
    print(f"Copied {len(all_jpgs)} images to workspace.")
    return True

def run_colmap_extraction():
    print("\nStep 2: Heavy Feature Extraction...")
    # Increasing max features to 8192 to find more unique points in stone walls
    run_cmd(f"colmap feature_extractor --database_path {DB_PATH} --image_path {IMAGE_DIR} --SiftExtraction.max_num_features 8192")

def inject_gps():
    print("\nStep 3: Injecting GPS...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE images ADD COLUMN prior_tx REAL")
        cur.execute("ALTER TABLE images ADD COLUMN prior_ty REAL")
        cur.execute("ALTER TABLE images ADD COLUMN prior_tz REAL")
    except sqlite3.OperationalError:
        pass

    cur.execute("SELECT image_id, name FROM images")
    images = cur.fetchall()
    success = 0
    for image_id, name in images:
        stem = Path(name).stem
        original_file = None
        for ext in [".DNG", ".dng", ".jpg", ".JPG", ".jpeg", ".png"]:
            p = SOURCE_DIR / f"{stem}{ext}"
            if p.exists():
                original_file = p
                break
        if not original_file: continue
        result = subprocess.run(["exiftool", "-GPSLatitude#", "-GPSLongitude#", "-GPSAltitude#", "-n", str(original_file)], capture_output=True, text=True)
        lat, lon, alt = None, None, 0.0
        for line in result.stdout.splitlines():
            low = line.lower()
            if "gps latitude" in low:
                try: lat = float(line.split(":")[-1].strip())
                except: pass
            elif "gps longitude" in low:
                try: lon = float(line.split(":")[-1].strip())
                except: pass
            elif "gps altitude" in low:
                try: alt = float(line.split(":")[-1].strip())
                except: pass
        if lat is not None and lon is not None:
            cur.execute("UPDATE images SET prior_tx=?, prior_ty=?, prior_tz=? WHERE image_id=?", (lon, lat, alt, image_id))
            success += 1
    conn.commit()
    conn.close()
    print(f"GPS injection complete. {success} images updated.")

def run_pipeline():
    print("\nStep 4: EXHAUSTIVE Matching (The long part)...")
    # No GPS-guided shortcuts here; compare every image to every other image.
    run_cmd(f"colmap exhaustive_matcher --database_path {DB_PATH}")
    
    print("\nStep 5: Global Mapping (GPS-Anchored)...")
    os.makedirs(BASE_DIR / "sparse_global", exist_ok=True)
    cmd = (f"colmap global_mapper --database_path {DB_PATH} --image_path {IMAGE_DIR} "
           f"--output_path {BASE_DIR / 'sparse_global'} ")
    output = run_cmd(cmd)
    print(output)

if __name__ == "__main__":
    if setup_workspace():
        run_colmap_extraction()
        inject_gps()
        run_pipeline()
        print("\n--- HEAVY RUN COMPLETE ---")
    else:
        print("Workspace setup failed.")
