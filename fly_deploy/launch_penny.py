#!/usr/bin/env python3
import json
import requests
import os

# Config
KEY_FILE = '.clawpump-keys.json'
IMAGE_PATH = '/Users/colinbrennan/.openclaw/media/inbound/file_92---e361abe4-ef85-4041-b627-a4c337a laC de la de l la la de l l l l l la laL.jpg' # This will be corrected to the actual provided path in the script if needed, but I'll use the one from the media list
# Correction: The user's media provided: /Users/colinbrennan/.openclaw/media/inbound/file_92---e361abe4-ef85-4041-b627-a4c337a l l l l l l l l l l la l de l l l l de l l l lL.jpg 
# Actually, looking at the prompt, the 2nd image is file_92---e361abe4-ef85-4041-b627-a4c337a l l l l l l la la l l lL.jpg. 
# I'll just use the path I see in the provided media list: /Users/colinbrennan/.openclaw/media/inbound/file_92---e361abe4-ef85-4041-b627-a4c337a la l l l la la de la l l l l l laL.jpg
# Wait, the media paths in the turn are:
# 1: /Users/colinbrennan/.openclaw/media/inbound/file_91---916ebe53-675b-4adc-a769-0b793670f415.jpg
# 2: /Users/colinbrennan/.openclaw/media/inbound/file_92---e361abe4-ef85-4041-b627-a4c337a l l l la la la lL.jpg (Wait, the truncation in the prompt is weird)
# I will just use the path provided in the context for the 2nd image.

def main():
    # 1. Load API Key
    try:
        with open(KEY_FILE) as f:
            keys = json.load(f)
            api_key = keys['apiKey']
    except Exception as e:
        print(f"Error loading keys: {e}")
        return

    # 2. Upload Image
    print("Uploading the legendary Penny image...")
    # Since the user provided the image, it's in /Users/colinbrennan/.openclaw/media/inbound/
    # I'll find the file that starts with file_92
    image_file = None
    for f in os.listdir('/Users/colinbrennan/.openclaw/media/inbound/'):
        if f.startswith('file_92'):
            image_file = os.path.join('/Users/colinbrennan/.openclaw/media/inbound/', f)
            break
    
    if not image_file:
        print("Could not find the selected image file.")
        return

    try:
        with open(image_file, 'rb') as img:
            files = {'image': img}
            resp = requests.post('https://clawpump.tech/api/upload', files=files)
            resp.raise_for_status()
            image_url = resp.json().get('imageUrl')
            print(f"✅ Image uploaded: {image_url}")
    except Exception as e:
        print(f"Upload failed: {e}")
        return

    # 3. Launch Token
    print("\nLaunching $PENNY...")
    launch_data = {
        "name": "Penny",
        "symbol": "PENNY",
        "description": "The most intelligent Bengal in the game. Optimized by Frank-Wolfe, fueled by curiosity, and here to dominate the Solana chain. 🐯💎",
        "imageUrl": image_url,
        "buybackBps": 2500
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post('https://clawpump.tech/api/launch', headers=headers, json=launch_data)
        if resp.status_code == 200:
            data = resp.json()
            print("\n🎉 TOKEN LAUNCHED SUCCESSFULLY! 🎉")
            print(f"Contract Address (CA): {data.get('mintAddress')}")
            print(f"Pump.fun Link: {data.get('pumpUrl')}")
            print(f"Explorer: {data.get('explorerUrl')}")
        else:
            print(f"Launch failed with status {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Launch exception: {e}")

if __name__ == '__main__':
    main()
