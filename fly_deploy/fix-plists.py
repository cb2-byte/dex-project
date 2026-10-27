#!/usr/bin/env python3
"""Fix launchd plist files to use correct Python path"""

import os

PYTHON_PATH = "/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"
WORKSPACE = "/Users/colinbrennan/.openclaw/workspace"

plists = [
    "eth-portfolio-bot.plist",
    "btc-portfolio-bot.plist", 
    "link-portfolio-bot.plist",
    "weather-portfolio-bot.plist"
]

for plist_name in plists:
    plist_path = os.path.join(WORKSPACE, plist_name)
    
    with open(plist_path, 'r') as f:
        content = f.read()
    
    # Replace python3 with full path
    content = content.replace(
        "<string>/usr/bin/python3</string>",
        f"<string>{PYTHON_PATH}</string>"
    )
    
    with open(plist_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {plist_name}")

print("\nAll plists updated with correct Python path")
print("Reload with: launchctl unload ... && launchctl load ...")
