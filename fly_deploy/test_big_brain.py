import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("NVIDIA_API_KEY")
IMAGE_PATH = "./gorey_castle/IMG_3818.jpg"
# Trying the model name from the email/launcher
MODEL_NAME = "minimax-m3" 
# We'll try the standard NIM completions endpoint
URL = "https://integrate.api.nvidia.com/v1/chat/completions"

def analyze():
    if not API_KEY:
        print("Error: NVIDIA_API_KEY not found.")
        return

    with open(IMAGE_PATH, "rb") as img_file:
        base64_image = base64.b64encode(img_file.read()).decode('utf-8')

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "This is an image from the Gorey Castle project. Perform a high-level spatial and architectural analysis. Describe the layout, the relationship between the water/land, and any architectural markers. Be extremely detailed and precise."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ],
        "max_tokens": 1000
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    print(f"Requesting analysis from {MODEL_NAME}...")
    try:
        response = requests.post(URL, headers=headers, json=payload, timeout=60)
        if response.status_code != 200:
            print(f"Error {response.status_code}: {response.text}")
            return
        
        result = response.json()['choices'][0]['message']['content']
        print("\n--- SPATIAL ANALYSIS REPORT ---\n")
        print(result)
    except Exception as e:
        print(f"Exception occurred: {e}")

if __name__ == "__main__":
    analyze()
