import hashlib
import hmac
import json
import base64
import sys
import os

# Adjust path to find app
sys.path.append(os.getcwd())

from app.config.license_manager import LicenseManager, SECRET_KEY as APP_KEY
# We can't easily import the key from key_gen.py because it's a script not a module structure we can easily hook without refactoring, 
# but we can read the file.

def get_key_from_keygen():
    with open("key_gen.py", "r") as f:
        for line in f:
            if "SECRET_KEY =" in line:
                # overly simple parse
                return line.split("=")[1].strip().strip("b").strip("'").strip('"')
    return None

print(f"App Key Bytes: {APP_KEY}")
print(f"App Key Hash: {hashlib.sha256(APP_KEY).hexdigest()}")

# Simulate Generation
hwid = "TEST_HWID"
data = {
    "hwid": hwid,
    "type": "lifetime",
    "date": None
}
json_str = json.dumps(data)
b64_payload = base64.b64encode(json_str.encode()).decode()
signature = hmac.new(APP_KEY, b64_payload.encode(), hashlib.sha256).hexdigest()
license_key = f"{b64_payload}.{signature}"

print(f"Generated Test Key: {license_key}")

# Simulate Verification via Class
lm = LicenseManager()
# Force HWID for test
lm.hwid = hwid 

print("Verifying with LicenseManager...")
is_valid, msg = lm.verify_key(license_key)
print(f"Result: {is_valid}, Message: {msg}")

if not is_valid:
    print("CRITICAL: Internal verification failed even with same key object!")
else:
    print("Internal verification passed. Problem is likely between key_gen.py and app.")
