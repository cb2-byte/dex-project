import os
import subprocess
import json
import time
import logging
import base64
import requests
from pathlib import Path
from dotenv import load_dotenv

# --- CONFIGURATION ---
IMAGE_DIR = Path("./gorey_castle")
PREVIEW_DIR = IMAGE_DIR / "previews"
ANALYSIS_FILE = IMAGE_DIR / "spatial_analysis.json"
LOG_FILE = IMAGE_DIR / "analysis_progress.log"
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
# Updated based on the exact code snippet provided by the user
MODEL_NAME = "nvidia/nemotron-3-ultra-550b-a55b" 

load_dotenv()
API_KEY = os.getenv("NVIDIA_API_KEY")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

def convert_dng_to_jpg(dng_path, jpg_path):
    try:
        subprocess.run(["sips", "-s", "format", "jpeg", str(dng_path), "--out", str(jpg_path)], 
                       check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to convert {dng_path}: {e}")
        return False

def analyze_image(image_path):
    with open(image_path, "rb") as img_file:
        base64_image = base64.b64encode(img_file.read()).decode('utf-8')

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this image of Gorey Castle. Describe the spatial layout, architectural features, and any key landmarks visible. Be precise and concise for a spatial map database."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ],
        "max_tokens": 500,
        "temperature": 1,
        "top_p": 0.95,
        # Adding the specific reasoning budget from the snippet
        "extra_body": {
            "chat_template_kwargs": {"enable_thinking": True},
            "reasoning_budget": 16384
        }
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(NVIDIA_API_URL, headers=headers, json=payload, timeout=300)
        if response.status_code == 404:
            logging.error(f"404 Error: Model {MODEL_NAME} not found on this endpoint.")
            return "ERROR_404"
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"API error for {image_path}: {e}")
        return None

def main():
    if not API_KEY:
        logging.error("NVIDIA_API_KEY not found in .env")
        return

    PREVIEW_DIR.mkdir(exist_ok=True)
    
    logging.info(f"Pre-flight check: Testing connection to {MODEL_NAME}...")
    test_img = next(IMAGE_DIR.glob("*.jpg"), None) or next(IMAGE_DIR.glob("*.png"), None)
    if test_img:
        res = analyze_image(test_img)
        if res == "ERROR_404":
            logging.error("CRITICAL: Model ID not found. Stopping to prevent loop.")
            return
        elif res is None:
            logging.error("CRITICAL: API Connection failed. Check key.")
            return
        logging.info("Pre-flight check SUCCESS. Starting grinder...")
    else:
        logging.warning("No sample images for pre-flight check. Proceeding anyway.")

    analysis_data = {}
    if ANALYSIS_FILE.exists():
        try:
            with open(ANALYSIS_FILE, "r") as f:
                analysis_data = json.load(f)
        except json.JSONDecodeError:
            analysis_data = {}

    all_files = []
    for ext in ["*.DNG", "*.jpg", "*.jpeg", "*.png"]:
        all_files.extend(list(IMAGE_DIR.glob(ext)))
        all_files.extend(list(IMAGE_DIR.glob(f"*.{ext.strip('*').lower()}")))
    all_files = list(set(all_files))
    logging.info(f"Found {len(all_files)} images to process.")

    for img_path in all_files:
        if img_path.name in analysis_data:
            continue

        logging.info(f"Processing {img_path.name}...")
        work_path = img_path
        if img_path.suffix.upper() == ".DNG":
            preview_path = PREVIEW_DIR / f"{img_path.stem}.jpg"
            if not preview_path.exists():
                if not convert_dng_to_jpg(img_path, preview_path):
                    continue
            work_path = preview_path
        elif img_path.suffix.lower() not in [".jpg", ".jpeg", ".png"]:
            preview_path = PREVIEW_DIR / f"{img_path.stem}.jpg"
            if not convert_dng_to_jpg(img_path, preview_path):
                continue
            work_path = preview_path

        result = analyze_image(work_path)
        if result and result != "ERROR_404":
            analysis_data[img_path.name] = {
                "analysis": result,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "original_file": str(img_path)
            }
            with open(ANALYSIS_FILE, "w") as f:
                json.dump(analysis_data, f, indent=2)
            logging.info(f"Successfully analyzed {img_path.name}")
        
        time.sleep(1) 

    logging.info("Finished all processing.")

if __name__ == "__main__":
    main()
