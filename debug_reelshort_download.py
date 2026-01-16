
import logging
import os
from app.platform_handler import download_with_ytdlp, extract_pinterest_direct_url

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_reelshort_download(url):
    print(f"\n--- Testing ReelShort Download: {url} ---")
    
    output_path = "DEBUG_DOWNLOADS"
    if not os.path.exists(output_path):
        os.makedirs(output_path)
        
    settings = {
        'video_enabled': True,
        'extension': 'mp4'
    }
    
    # 1. Try Generic yt-dlp
    print("\n[Step 1] Trying Generic yt-dlp...")
    def progress(p):
        print(f"Progress: {p}%", end='\r')
        
    success, msg = download_with_ytdlp(url, output_path, progress, settings)
    print(f"\nResult: {success}, Message: {msg}")
    
    if success:
        print("Generic download worked!")
        return

    # 2. Try Fallback Extraction
    print("\n[Step 2] Trying Playwright Extraction (Fallback)...")
    direct_url = extract_pinterest_direct_url(url)
    
    if direct_url:
        print(f"Found Direct URL: {direct_url}")
        print("Attempting download of direct URL...")
        success, msg = download_with_ytdlp(direct_url, output_path, progress, settings)
        print(f"\nResult: {success}, Message: {msg}")
    else:
        print("Fallback extraction failed. No video URL found.")

if __name__ == "__main__":
    # URL provided by user previously
    test_url = "https://www.reelshort.com/episodes/episode-1-the-billionaire-female-ceo-from-the-trailer-park-6858fb34698cc855a209fe28-mktu6zb0hi?play_time=1"
    test_reelshort_download(test_url)
