import hashlib
import hmac
import json
import base64
import argparse
from datetime import datetime, timedelta

# MUST MATCH THE KEY IN app/config/license_manager.py
SECRET_KEY = b"super_secret_video_downloader_key_2025_v1"

def generate_license(hwid, days=None):
    """
    Generates a signed license key.
    hwid: User's Machine ID
    days: Number of days valid (None for Lifetime)
    """
    data = {
        "hwid": hwid,
        "type": "lifetime" if days is None else "expires",
        "date": (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d") if days else None
    }
    
    json_str = json.dumps(data)
    b64_payload = base64.b64encode(json_str.encode()).decode()
    
    signature = hmac.new(SECRET_KEY, b64_payload.encode(), hashlib.sha256).hexdigest()
    
    return f"{b64_payload}.{signature}"

if __name__ == "__main__":
    print("--- Video Downloader Key Generator ---")
    target_hwid = input("Enter User HWID: ").strip()
    duration = input("Enter duration in days (or press Enter for Lifetime): ").strip()
    
    if not duration:
        key = generate_license(target_hwid, days=None)
        print(f"\n[LIFETIME KEY GENERATED]\n{key}\n")
    else:
        try:
            d = int(duration)
            key = generate_license(target_hwid, days=d)
            print(f"\n[{d} DAY KEY GENERATED]\n{key}\n")
        except ValueError:
            print("Invalid duration number.")
