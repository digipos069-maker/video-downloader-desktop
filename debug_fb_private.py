
import asyncio
from app.platform_handler import PlatformHandlerFactory, download_with_ytdlp
from app.config.credentials import CredentialsManager
import logging
import os

# -- CONFIGURATION --
# The URL you provided
FACEBOOK_URL = "https://www.facebook.com/profile.php?id=100093545089321&sk=reels_tab"
# Set a path for the test download
DOWNLOAD_PATH = os.path.join(os.getcwd(), "DEBUG_DOWNLOADS")
# -----------------

# --- Setup logging to console for immediate feedback ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger()

async def main():
    log.info("--- STARTING FACEBOOK DOWNLOAD DEBUG SCRIPT ---")

    if not os.path.exists(DOWNLOAD_PATH):
        os.makedirs(DOWNLOAD_PATH)
        log.info(f"Created download directory: {DOWNLOAD_PATH}")

    # 1. Initialize handlers and managers
    handler_factory = PlatformHandlerFactory()
    creds_manager = CredentialsManager()
    
    # 2. Get the appropriate handler for the URL
    handler = handler_factory.get_handler(FACEBOOK_URL)
    if not handler:
        log.error(f"Could not find a handler for the URL: {FACEBOOK_URL}")
        return

    # 3. Get credentials and settings for scraping
    log.info("Loading credentials for scraping...")
    scrape_settings = {}
    fb_creds = creds_manager.get_credential('facebook')
    if not fb_creds or not fb_creds.get('cookie_file'):
        log.error("Facebook cookie file not configured in credentials. Please set it up via the Settings tab.")
        return
        
    scrape_settings['cookie_file'] = fb_creds.get('cookie_file')
    log.info(f"Using cookie file: {scrape_settings['cookie_file']}")

    # 4. Scrape the page to get video URLs
    log.info(f"Scraping URL: {FACEBOOK_URL}")
    try:
        # Use an asyncio loop since our app is async, but run the sync function in an executor
        loop = asyncio.get_event_loop()
        video_metadata_list = await loop.run_in_executor(
            None, handler.get_playlist_metadata, FACEBOOK_URL, 10, scrape_settings
        )
        if not video_metadata_list:
            log.error("Scraping did not return any video links. The page might be private, require a login not covered by the cookie, or have no videos.")
            return
        log.info(f"Scraping finished. Found {len(video_metadata_list)} items.")

    except Exception as e:
        log.error(f"An error occurred during scraping: {e}", exc_info=True)
        return
        
    # 5. Attempt to download each video
    for i, metadata in enumerate(video_metadata_list):
        video_url = metadata.get('url')
        log.info(f"--- ATTEMPTING DOWNLOAD [{i+1}/{len(video_metadata_list)}]: {video_url} ---")
        
        # Prepare settings for the download
        download_settings = {
            'video_path': DOWNLOAD_PATH,
            'cookie_file': scrape_settings['cookie_file'] # Pass the same cookie file
        }
        
        # Simple progress callback for console
        def progress(p):
            print(f"Progress: {p}%", end='\r')

        try:
            success = await loop.run_in_executor(
                None, download_with_ytdlp, video_url, DOWNLOAD_PATH, progress, download_settings
            )
            if success:
                log.info(f"SUCCESS: Download completed for {video_url}")
            else:
                log.error(f"FAILED: Download function returned False for {video_url}")
        except Exception as e:
            log.error(f"CRITICAL FAILURE: An exception occurred while trying to download {video_url}", exc_info=True)
        
        print("\n") # Newline after progress bar

if __name__ == "__main__":
    asyncio.run(main())
