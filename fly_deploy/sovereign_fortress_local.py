#!/usr/bin/env python3
"""
sovereign_fortress_local.py — Gorey Castle photogrammetry pipeline
Local Sparse Reconstruction (M4) -> Cloud Dense Mesh
"""

import subprocess, os, sys
from pathlib import Path

# ── config ────────────────────────────────────────────────────────────────────
IMAGE_DIR = Path("./colmap_workspace/images")
WORKSPACE = Path("./colmap_workspace")
OUTPUT_DIR = Path("./output")
DATABASE = WORKSPACE / "database.db"
SPARSE_DIR = WORKSPACE / "sparse"
DENSE_DIR = WORKSPACE / "dense"

COLMAP = "colmap" 

def run(cmd: list, **kw):
    print(f"\n▶ {' '.join(str(c) for c in cmd)}\n")
    subprocess.run(cmd, check=True, **kw)

# ── 1. feature extraction ─────────────────────────────────────────────────────
def extract_features():
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    SPARSE_DIR.mkdir(parents=True, exist_ok=True)
    # On Mac M4, COLMAP uses Metal automatically. 
    # We remove GPU_INDEX since that's for NVIDIA/CUDA.
    run([COLMAP, "feature_extractor",
        "--database_path", str(DATABASE),
        "--image_path", str(IMAGE_DIR),
        "--ImageReader.single_camera", "1",
    ])

# ── 2. sequential matching ────────────────────────────────────────────────────
def match_features():
    run([COLMAP, "sequential_matcher",
        "--database_path", str(DATABASE),
        "--SequentialMatching.overlap", "10",
    ])

# ── 3. sparse reconstruction (mapper) ─────────────────────────────────────────
def sparse_reconstruct():
    run([COLMAP, "mapper",
        "--database_path", str(DATABASE),
        "--image_path", str(IMAGE_DIR),
        "--output_path", str(SPARSE_DIR),
    ])

# ── main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    steps = [extract_features, match_features, sparse_reconstruct]
    for step in steps:
        try:
            step()
        except Exception as e:
            print(f"\n❌ Step failed: {e}")
            sys.exit(1)
    print("\n🏰 Sparse reconstruction complete — ready for cloud dense pass.")
