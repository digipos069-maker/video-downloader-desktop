
import urllib.request
import traceback
import os

url = "https://v-mps.crazymaplestudios.com/activity/mp4/10001_0100.mp4"
output_path = "DEBUG_DOWNLOADS/test_video.mp4"

if not os.path.exists("DEBUG_DOWNLOADS"):
    os.makedirs("DEBUG_DOWNLOADS")

print(f"Attempting download: {url}")

try:
    # 1. Simple request
    print("1. Trying simple urlretrieve...")
    urllib.request.urlretrieve(url, output_path)
    print("Success!")
except Exception:
    print("Simple download failed:")
    traceback.print_exc()
    
    try:
        # 2. Request with Headers
        print("\n2. Trying with User-Agent header...")
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')]
        urllib.request.install_opener(opener)
        urllib.request.urlretrieve(url, output_path)
        print("Success with headers!")
    except Exception:
        print("Download with headers failed:")
        traceback.print_exc()
