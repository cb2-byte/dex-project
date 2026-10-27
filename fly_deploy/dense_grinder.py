import os
import subprocess
from pathlib import Path

# --- SETTINGS ---
BASE_DIR = Path("/Volumes/Lexar/colmap_workspace")
IMAGE_DIR = BASE_DIR / "images"
SPARSE_DIR = BASE_DIR / "sparse_final"
DENSE_DIR = BASE_DIR / "dense"

def run_cmd(cmd):
    print(f"Running: {cmd}")
    # We don't use capture_output=True here because dense reconstruction 
    # produces massive amounts of output that can fill the buffer.
    # Instead, we rely on the shell redirection to the log file.
    res = subprocess.run(cmd, shell=True)
    if res.returncode != 0:
        print(f"Error encountered during: {cmd}")
    return res.returncode

def run_dense_pipeline():
    print("\n--- STARTING DENSE RECONSTRUCTION ---")
    
    # 1. Undistort Images
    print("\nStep 1: Undistorting Images...")
    # We use the folder containing the .bin files directly
    run_cmd(f"colmap image_undistorter --image_path {IMAGE_DIR} --input_path {SPARSE_DIR.parent} --output_path {DENSE_DIR}")
    
    # VERIFICATION: Check if undistorted images were actually created
    undistorted_images = DENSE_DIR / "images"
    if not undistorted_images.exists() or not any(undistorted_images.iterdir()):
        print("CRITICAL ERROR: Undistortion failed. No images found in dense/images. Stopping pipeline.")
        return
    
    # 2. Patch Match Stereo (The laaaaang part)
    print("\nStep 2: Patch Match Stereo (Depth Map Generation)...")
    print("Note: This is the most CPU-intensive part and will take many hours.")
    run_cmd(f"colmap patch_match_stereo --workspace_path {DENSE_DIR}")
    
    # 3. Stereo Fusion
    print("\nStep 3: Stereo Fusion (Merging Depth Maps)...")
    output_ply = DENSE_DIR / "fused.ply"
    run_cmd(f"colmap stereo_fusion --workspace_path {DENSE_DIR} --output_path {output_ply}")
    
    # 4. Meshing
    print("\nStep 4: Poisson Meshing (Creating the solid surface)...")
    output_mesh = DENSE_DIR / "mesh.ply"
    run_cmd(f"colmap poisson_mesher --input_path {output_ply} --output_path {output_mesh}")
    
    print("\n--- DENSE RECONSTRUCTION COMPLETE ---")
    print(f"Final Model: {output_mesh}")

if __name__ == "__main__":
    try:
        run_dense_pipeline()
    except Exception as e:
        print(f"Pipeline failed: {e}")
