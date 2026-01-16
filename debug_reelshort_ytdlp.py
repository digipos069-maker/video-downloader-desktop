
import logging
import os
from app.platform_handler import download_with_ytdlp

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_ytdlp_m3u8():
    url = "https://v-mps.crazymaplestudios.com/vod-112094/4038b09cec3d71f0800f3108f4940102/b55370f2b8c844d6aa010fb38611147d-ad4b1a36866a5def71c009b313f4dd0e-sd.m3u8"
    print(f"\n--- Testing yt-dlp with m3u8: {url} ---")
    
    output_path = "DEBUG_DOWNLOADS"
    if not os.path.exists(output_path):
        os.makedirs(output_path)
        
    settings = {
        'video_enabled': True,
        'extension': 'mp4',
        'naming_style': 'Original Name'
    }
    
    def progress(p):
        print(f"Progress: {p}%", end='\r')
        
    success, msg = download_with_ytdlp(url, output_path, progress, settings)
    print(f"\nResult: {success}, Message: {msg}")

if __name__ == "__main__":
    test_ytdlp_m3u8()
