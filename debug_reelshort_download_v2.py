
import logging
import os
from app.platform_handler import download_with_ytdlp, extract_pinterest_direct_url, download_direct

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_reelshort_download(url):
    print(f"\n--- Testing ReelShort Download V2: {url} ---")
    
    output_path = "DEBUG_DOWNLOADS"
    if not os.path.exists(output_path):
        os.makedirs(output_path)
        
    settings = {
        'video_enabled': True,
        'extension': 'mp4',
        'naming_style': 'Original Name'
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
        
        # 3. Try Direct Download (urllib)
        print("\n[Step 3] Attempting Direct Download (urllib) with headers...")
        success, msg = download_direct(direct_url, output_path, 'ReelShort_Debug_Video', progress, settings)
        print(f"\nResult: {success}, Message: {msg}")
    else:
        print("Fallback extraction failed. No video URL found.")

if __name__ == "__main__":
    test_url = "https://www.reelshort.com/episodes/episode-57-step-aside-i-m-the-king-of-capital-690306d7afd90472c800cf3a-76bwqt9pjq"
    test_reelshort_download(test_url)
