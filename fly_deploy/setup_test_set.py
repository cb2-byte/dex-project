import os
import shutil
from pathlib import Path

src_dir = Path("./gorey_castle")
dst_dir = Path("./colmap_workspace/images")
dst_dir.mkdir(parents=True, exist_ok=True)

# Get all image files and sort them
images = sorted([f for f in src_dir.iterdir() if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".dng"]])

# Take every 9th image to get a spatial bridge
test_set = images[::9]

# Copy files
count = 0
for img in test_set:
    shutil.copy2(img, dst_dir / img.name)
    count += 1

print(f"Successfully copied {count} images to {dst_dir}")
