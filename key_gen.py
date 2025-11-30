import hashlib
import hmac
import json
import base64
from datetime import datetime, timedelta

# Use the exact same byte string logic
SECRET_KEY = b"super_secret_video_downloader_key_2025_v1"

def generate_license(hwid, days=None):
    data = {
        "hwid": hwid,
        "type": "lifetime" if days is None else "expires",
        "date": (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d") if days else None
    }
    # Ensure separators match default Python json.dumps (which are (', ', ': '))
    # If app uses default json.loads, it doesn't matter for decoding, 
    # BUT it matters for re-encoding if the app were to re-encode (which it doesn't).
    # However, the signature is on the b64 string.
    
    json_str = json.dumps(data)
    b64_payload = base64.b64encode(json_str.encode()).decode()
    
    signature = hmac.new(SECRET_KEY, b64_payload.encode(), hashlib.sha256).hexdigest()
    
    return f"{b64_payload}.{signature}"

if __name__ == "__main__":
    print("--- Video Downloader Key Generator ---")
    target_hwid = input("Enter User HWID: ").strip()
    duration = input("Enter duration in days (or press Enter for Lifetime): ").strip()
    
    # Sanity check on the key being used
    print(f"DEBUG: Signing with Key Hash: {hashlib.sha256(SECRET_KEY).hexdigest()}")
    
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