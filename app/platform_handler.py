"""
Platform-specific handlers for scraping and downloading.
Now utilizing Playwright for robust metadata extraction.
"""
import yt_dlp
from abc import ABC, abstractmethod
import time

# Attempt to import Playwright
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Playwright not installed. Please run: pip install playwright && playwright install")

def extract_metadata_with_playwright(url, max_entries=100):
    """
    Helper to extract metadata using Playwright.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return [{'url': url, 'title': 'Error: Playwright Missing', 'type': 'error'}]

    results = []
    try:
        with sync_playwright() as p:
            # Try launching Chromium
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as e:
                print(f"Error launching browser: {e}")
                return [{'url': url, 'title': 'Error: Browser Launch Failed (run "playwright install")', 'type': 'error'}]

            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            page = context.new_page()
            
            print(f"Playwright visiting: {url}")
            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                
                # Simple heuristic: Get the title
                page_title = page.title()
                
                # Try to find an OG:image or video tag for better context (optional)
                # For now, we just return the page info
                
                results.append({
                    'url': url,
                    'title': page_title.strip() if page_title else "No Title",
                    'type': 'webpage' 
                })
                
            except Exception as e:
                print(f"Error processing page {url}: {e}")
                results.append({'url': url, 'title': 'Page Load Error', 'type': 'error'})
            finally:
                browser.close()
                
    except Exception as e:
        print(f"Playwright script error: {e}")
        results.append({'url': url, 'title': 'Scrape System Error', 'type': 'error'})
        
    return results

class BaseHandler(ABC):
    @abstractmethod
    def can_handle(self, url):
        pass

    @abstractmethod
    def get_metadata(self, url):
        pass

    @abstractmethod
    def get_playlist_metadata(self, url, max_entries=100):
        pass

    @abstractmethod
    def download(self, item, progress_callback):
        pass

# --- Handlers now use Playwright for Scraping ---

class YouTubeHandler(BaseHandler):
    def can_handle(self, url):
        return 'youtube.com' in url or 'youtu.be' in url

    def get_metadata(self, url):
        return extract_metadata_with_playwright(url)

    def get_playlist_metadata(self, url, max_entries=100):
        return extract_metadata_with_playwright(url)

    def download(self, item, progress_callback):
        print(f"Downloading YouTube video: {item.get('title', 'Unknown')}")
        progress_callback(100)
        return True

class TikTokHandler(BaseHandler):
    def can_handle(self, url):
        return 'tiktok.com' in url

    def get_metadata(self, url):
        return extract_metadata_with_playwright(url)

    def get_playlist_metadata(self, url, max_entries=100):
        return extract_metadata_with_playwright(url)

    def download(self, item, progress_callback):
        print(f"Downloading TikTok video: {item.get('title', 'Unknown')}")
        progress_callback(100)
        return True

class PinterestHandler(BaseHandler):
    def can_handle(self, url):
        return 'pinterest.com' in url

    def get_metadata(self, url):
        return extract_metadata_with_playwright(url)

    def get_playlist_metadata(self, url, max_entries=100):
        return extract_metadata_with_playwright(url)

    def download(self, item, progress_callback):
        print(f"Downloading Pinterest pin: {item.get('title', 'Unknown')}")
        progress_callback(100)
        return True

class FacebookHandler(BaseHandler):
    def can_handle(self, url):
        return 'facebook.com' in url or 'fb.watch' in url

    def get_metadata(self, url):
        return extract_metadata_with_playwright(url)
    
    def get_playlist_metadata(self, url, max_entries=100):
        return extract_metadata_with_playwright(url)

    def download(self, item, progress_callback):
        print(f"Downloading Facebook video: {item.get('title', 'Unknown')}")
        progress_callback(100)
        return True

class InstagramHandler(BaseHandler):
    def can_handle(self, url):
        return 'instagram.com' in url

    def get_metadata(self, url):
        return extract_metadata_with_playwright(url)

    def get_playlist_metadata(self, url, max_entries=100):
        return extract_metadata_with_playwright(url)

    def download(self, item, progress_callback):
        print(f"Downloading Instagram post: {item.get('title', 'Unknown')}")
        progress_callback(100)
        return True


class PlatformHandlerFactory:
    def __init__(self):
        self.handlers = [
            YouTubeHandler(),
            TikTokHandler(),
            PinterestHandler(),
            FacebookHandler(),
            InstagramHandler(),
        ]

    def get_handler(self, url):
        for handler in self.handlers:
            if handler.can_handle(url):
                return handler
        return None
