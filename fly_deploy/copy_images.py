import shutil
from pathlib import Path

src_list = Path("./gorey_castle/test_set_list.txt")
dst_dir = Path("./colmap_workspace/images")

if not src_list.exists():
    print("Error: list file not found")
    exit(1)

dst_dir.mkdir(parents=True, exist_ok=True)

with open(src_list, "r") as f:
    files = [line.strip() for line in f if line.strip()]

count = 0
for f_path in files:
    p = Path(f_path)
    if p.exists():
        shutil.copy2(p, dst_dir / p.name)
        count += 1

print(f"Copied {count} files to {dst_dir}")
