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
    print("Step 1: Cleaning workspace...")
    if BASE_DIR.exists():
        # Handle symlink by cleaning contents of the target
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
        print("Error: No JPG/PNG images found in source directory!")
        return False

    # Full set of images for maximum reconstruction quality
    test_set = all_jpgs
    
    for img in test_set:
        shutil.copy2(img, IMAGE_DIR / img.name)
    
    print(f"Copied {len(test_set)} images to workspace (Full Set).")
    return len(test_set) > 0

def run_colmap_extraction():
    print("\nStep 2: Extracting Features (Creating DB)...")
    run_cmd(f"colmap feature_extractor --database_path {DB_PATH} --image_path {IMAGE_DIR}")

def inject_gps():
    print("\nStep 3: Injecting GPS from RAW source...")
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
    return success

def run_pipeline():
    print("\nStep 4: Spatial Matching (GPS-Guided)...")
    run_cmd(f"colmap spatial_matcher --database_path {DB_PATH} --SpatialMatching.max_num_neighbors 100 --SpatialMatching.ignore_z 1")
    
    print("\nStep 5: Mapping (Reconstruction)...")
    os.makedirs(BASE_DIR / "sparse", exist_ok=True)
    # Implementing the "Relaxed" constraints for the first pass
    cmd = (f"colmap mapper --database_path {DB_PATH} --image_path {IMAGE_DIR} "
           f"--output_path {BASE_DIR / 'sparse'} "
           f"--Mapper.init_min_num_inliers 20 "
           f"--Mapper.init_max_forward_motion 0.95 "
           f"--Mapper.multiple_models 0")
    output = run_cmd(cmd)
    print(output)

if __name__ == "__main__":
    if setup_workspace():
        run_colmap_extraction()
        inject_gps()
        run_pipeline()
        print("\n--- FINAL REPORT ---")
        try:
            res = subprocess.run(f"sqlite3 {DB_PATH} \"SELECT COUNT(*) FROM images WHERE prior_tx IS NOT NULL;\"", shell=True, capture_output=True, text=True)
            print(f"Database Verified GPS Count: {res.stdout.strip()}")
        except:
            print("Could not verify GPS count.")
    else:
        print("Workspace setup failed.")
