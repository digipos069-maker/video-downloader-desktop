import hashlib
import platform
import subprocess
import os
import json
import base64
import hmac
import time
from datetime import datetime, timedelta

# SECURITY WARNING: In a production app, obfuscate this key or use a compiled language for the core verifier.
# For this Python app, we use a hardcoded secret. 
# YOU (The Admin) must use this SAME secret in your key_gen.py script.
SECRET_KEY = b"super_secret_video_downloader_key_2025_v1"

class LicenseManager:
    def __init__(self, license_file_path="license.dat"):
        self.license_file_path = license_file_path
        self.hwid = self.get_hwid()

    def get_hwid(self):
        """Generates a unique Hardware ID based on system properties."""
        try:
            system_info = [
                platform.node(),
                platform.architecture()[0],
                platform.machine(),
                platform.processor()
            ]
            
            # Try to get disk serial number (Windows) for stronger locking
            if platform.system() == "Windows":
                try:
                    cmd = 'wmic diskdrive get serialnumber'
                    serial = subprocess.check_output(cmd, shell=True).decode().split('\n')[1].strip()
                    system_info.append(serial)
                except:
                    pass
            
            data_str = "".join(system_info)
            return hashlib.sha256(data_str.encode()).hexdigest().upper()[:32]
        except Exception:
            return "UNKNOWN_HWID"

    def verify_key(self, license_key):
        """
        Verifies a license key.
        Format: BASE64_PAYLOAD.SIGNATURE
        Payload JSON: {"hwid": "...", "type": "lifetime"|"expires", "date": "YYYY-MM-DD"|None}
        """
        try:
            if not license_key or "." not in license_key:
                return False, "Invalid key format"

            b64_payload, signature = license_key.split(".")
            
            # 1. Verify Signature
            expected_sig = hmac.new(SECRET_KEY, b64_payload.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected_sig, signature):
                return False, "Invalid license signature"

            # 2. Decode Payload
            payload_json = base64.b64decode(b64_payload).decode()
            data = json.loads(payload_json)

            # 3. Check HWID
            if data.get("hwid") != self.hwid:
                return False, "License key is for a different machine"

            # 4. Check Expiration
            if data.get("type") == "lifetime":
                return True, "Lifetime License Active"
            
            expiry_str = data.get("date")
            if expiry_str:
                expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
                if datetime.now() > expiry_date:
                    return False, f"License expired on {expiry_str}"
                return True, f"Active until {expiry_str}"
            
            return False, "Invalid license data"

        except Exception as e:
            return False, f"Verification error: {str(e)}"

    def save_license(self, key):
        """Saves the license key to a local file."""
        try:
            with open(self.license_file_path, "w") as f:
                f.write(key)
            return True
        except Exception:
            return False

    def load_license(self):
        """Loads the license key from disk."""
        if not os.path.exists(self.license_file_path):
            return None
        try:
            with open(self.license_file_path, "r") as f:
                return f.read().strip()
        except:
            return None

    def get_license_status(self):
        """Returns (is_valid, message, details_dict)."""
        key = self.load_license()
        if not key:
            return False, "No license found", None
        
        is_valid, msg = self.verify_key(key)
        return is_valid, msg, key
