#!/usr/bin/env python3
"""
sovereign_fortress.py — Gorey Castle photogrammetry pipeline
COLMAP -> dense mesh -> UE5-ready output
"""

import subprocess, os, sys
from pathlib import Path

# ── config ────────────────────────────────────────────────────────────────────
IMAGE_DIR = Path("/home/shadeform/images") # your 1,300 iPhone RAWs
WORKSPACE = Path("/home/shadeform/colmap_workspace")
OUTPUT_DIR = Path("/home/shadeform/output")
DATABASE = WORKSPACE / "database.db"
SPARSE_DIR = WORKSPACE / "sparse"
DENSE_DIR = WORKSPACE / "dense"

COLMAP = "colmap" # or full path if not on $PATH
GPU_INDEX = "0" # Brev pod GPU

def run(cmd: list, **kw):
    print(f"\n▶ {' '.join(str(c) for c in cmd)}\n")
    subprocess.run(cmd, check=True, **kw)

# ── 1. feature extraction ─────────────────────────────────────────────────────
def extract_features():
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    SPARSE_DIR.mkdir(parents=True, exist_ok=True)
    run([COLMAP, "feature_extractor",
        "--database_path", str(DATABASE),
        "--image_path", str(IMAGE_DIR),
        "--ImageReader.single_camera", "1",
        "--SiftExtraction.use_gpu", "1",
        "--SiftExtraction.gpu_index", GPU_INDEX,
        "--SiftExtraction.max_num_features", "16384",
    ])

# ── 2. sequential matching ────────────────────────────────────────────────────
def match_features():
    run([COLMAP, "sequential_matcher",
        "--database_path", str(DATABASE),
        "--SiftMatching.use_gpu", "1",
        "--SiftMatching.gpu_index", GPU_INDEX,
        "--SequentialMatching.overlap", "10", # look 10 frames ahead/behind
    ])

# ── 3. sparse reconstruction (mapper) ─────────────────────────────────────────
def sparse_reconstruct():
    run([COLMAP, "mapper",
        "--database_path", str(DATABASE),
        "--image_path", str(IMAGE_DIR),
        "--output_path", str(SPARSE_DIR),
    ])

# ── 4. dense reconstruction ───────────────────────────────────────────────────
def dense_reconstruct():
    DENSE_DIR.mkdir(parents=True, exist_ok=True)
    # undistort images first
    # We assume the mapper output is in SPARSE_DIR/0
    run([COLMAP, "image_undistorter",
        "--image_path", str(IMAGE_DIR),
        "--input_path", str(SPARSE_DIR / "0"),
        "--output_path", str(DENSE_DIR),
        "--output_type", "COLMAP",
    ])
    # patch match stereo (GPU)
    run([COLMAP, "patch_match_stereo",
        "--workspace_path", str(DENSE_DIR),
        "--workspace_format", "COLMAP",
        "--PatchMatchStereo.geom_consistency", "true",
    ])
    # fuse into point cloud
    run([COLMAP, "stereo_fusion",
        "--workspace_path", str(DENSE_DIR),
        "--workspace_format", "COLMAP",
        "--input_type", "geometric",
        "--output_path", str(DENSE_DIR / "fused.ply"),
    ])

# ── 5. mesh + texture (via open3d or meshlab post-step) ───────────────────────
def export_mesh():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Poisson surface reconstruction — requires open3d
    try:
        import open3d as o3d
        pcd = o3d.io.read_point_cloud(str(DENSE_DIR / "fused.ply"))
        pcd.estimate_normals()
        mesh, _ = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=11)
        out = OUTPUT_DIR / "gorey_castle.obj"
        o3d.io.write_triangle_mesh(str(out), mesh)
        print(f"\n✅ Mesh written → {out}")
    except ImportError:
        print("\n❌ Open3D not installed. Skipping Poisson Mesh export.")
        print("The dense cloud is still available at /home/ubuntu/colmap_workspace/dense/fused.ply")

# ── main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    steps = [extract_features, match_features, sparse_reconstruct,
              dense_reconstruct, export_mesh]
    for step in steps:
        try:
            step()
        except Exception as e:
            print(f"\n❌ Step failed: {e}")
            sys.exit(1)
    print("\n🏰 Sovereign Fortress pipeline complete.")
