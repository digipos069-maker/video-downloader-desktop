import logging
import sys
import os
# Ensure 'app' is in path
sys.path.append(os.getcwd())

from app.platform_handler import extract_metadata_with_playwright

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("debug_fb_scrape.log", mode='w', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def run_debug():
    # Target URL (Profile from logs)
    url = "https://www.facebook.com/profile.php?id=61579938422467"
    
    # Mock Settings - Mimicking what the app SHOULD pass
    # CRITICAL: Ensure cookie_file matches the one in the user's logs
    settings = {
        "cookie_file": "C:/Users/USER/Downloads/www.facebook.com_cookies.txt",
        "cookies_from_browser": "chrome" 
    }
    
    print(f"Starting debug scrape for: {url}")
    print(f"Using settings: {settings}")
    
    if not os.path.exists(settings["cookie_file"]):
        print(f"WARNING: Cookie file not found at {settings['cookie_file']}")
    
    # Call the function directly
    try:
        results = extract_metadata_with_playwright(url, max_entries=50, settings=settings)
        
        print(f"\n--- Scrape Results ---")
        print(f"Total Items Found: {len(results)}")
        for i, item in enumerate(results):
            print(f"{i+1}. {item['url']} ({item.get('type')})")
            
    except Exception as e:
        print(f"Fatal Error: {e}")

if __name__ == "__main__":
    run_debug()
