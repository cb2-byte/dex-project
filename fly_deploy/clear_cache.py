#!/usr/bin/env python3
import shutil
import os
cache_dir = os.path.join(os.path.dirname(__file__), '__pycache__')
if os.path.exists(cache_dir):
    shutil.rmtree(cache_dir)
    print(f"Deleted {cache_dir}")
else:
    print("No cache to delete")
