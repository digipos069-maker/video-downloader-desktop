"""
Platform-specific handlers for scraping and downloading.
Now utilizing Playwright for robust metadata extraction.
"""
import yt_dlp
from abc import ABC, abstractmethod
import time
from urllib.parse import urlparse
import logging

# Configure logging
logging.basicConfig(
    filename='debug_log.txt',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Attempt to import Playwright
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logging.error("Playwright not installed. Please run: pip install playwright && playwright install")

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
                logging.error(f"Error launching browser: {e}")
                return [{'url': url, 'title': 'Error: Browser Launch Failed (run "playwright install")', 'type': 'error'}]

            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            page = context.new_page()
            
            logging.info(f"Playwright visiting: {url}")
            try:
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                
                # Scroll to fetch more content (simulate lazy loading)
                # Increased scroll iterations for Pinterest
                for i in range(10): 
                    page.mouse.wheel(0, 15000)
                    time.sleep(1.5) # Increased wait time
                    logging.debug(f"Scroll iteration {i+1}/10 completed")

                # Parse the domain to filter links
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.replace('www.', '') # Remove www for broader matching
                
                # Extract links
                extracted_links = page.evaluate("""
                    () => {
                        return Array.from(document.querySelectorAll('a[href]')).map(a => ({
                            url: a.href,
                            text: a.innerText
                        }));
                    }
                """)
                
                logging.info(f"Found {len(extracted_links)} raw links on page.")

                unique_urls = set()
                count = 0
                
                for link in extracted_links:
                    href = link['url']
                    text = link['text'] or "Scraped Link"
                    
                    # Basic filtering
                    if href in unique_urls:
                        continue
                        
                    if not href.startswith('http'):
                        continue
                        
                    # Check if link belongs to same domain (fuzzy match)
                    # Special handling for Pinterest pins
                    is_pin = 'pinterest.com/pin/' in href
                    
                    if domain not in href and not is_pin:
                        continue
                    
                    # If it's a pinterest search or board, we specifically want /pin/ links usually
                    if 'pinterest.com' in domain and not is_pin:
                        # Optional: skip non-pin links if we are on pinterest?
                        # For now, keep them but prioritize pins effectively by order
                        pass

                    unique_urls.add(href)
                    results.append({
                        'url': href,
                        'title': text.strip(),
                        'type': 'scraped_link'
                    })
                    
                    count += 1
                    if count >= max_entries:
                        break
                
                logging.info(f"Filtered down to {len(results)} unique valid links.")

                if not results:
                    logging.warning("No links found after filtering. Returning page fallback.")
                    # Fallback: just return the page itself
                    page_title = page.title()
                    results.append({
                        'url': url,
                        'title': page_title.strip() if page_title else "No Title",
                        'type': 'webpage' 
                    })
                
            except Exception as e:
                logging.error(f"Error processing page {url}: {e}")
                results.append({'url': url, 'title': 'Page Load Error', 'type': 'error'})
            finally:
                browser.close()
                
    except Exception as e:
        logging.error(f"Playwright script error: {e}")
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

    def get_download_path(self, settings, is_video=True):
        """Helper to determine the download path from settings."""
        if is_video:
            return settings.get('video_path') or settings.get('photo_path') or '.'
        else:
            return settings.get('photo_path') or settings.get('video_path') or '.'

# --- Handlers now use Playwright for Scraping ---

class YouTubeHandler(BaseHandler):
    def can_handle(self, url):
        return 'youtube.com' in url or 'youtu.be' in url

    def get_metadata(self, url):
        return extract_metadata_with_playwright(url)

    def get_playlist_metadata(self, url, max_entries=100):
        return extract_metadata_with_playwright(url)

    def download(self, item, progress_callback):
        url = item['url']
        settings = item.get('settings', {})
        output_path = self.get_download_path(settings, is_video=True)
        
        logging.info(f"Starting YouTube download for {url} to {output_path}")
        
        ydl_opts = {
            'outtmpl': f'{output_path}/%(title)s.%(ext)s',
            'progress_hooks': [lambda d: progress_callback(int(float(d.get('downloaded_bytes', 0)) / float(d.get('total_bytes', 1)) * 100)) if d['status'] == 'downloading' else None],
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            logging.info(f"YouTube download completed: {url}")
            progress_callback(100)
            return True
        except Exception as e:
            logging.error(f"YouTube download failed: {e}")
            return False

class TikTokHandler(BaseHandler):
    def can_handle(self, url):
        return 'tiktok.com' in url

    def get_metadata(self, url):
        return extract_metadata_with_playwright(url)

    def get_playlist_metadata(self, url, max_entries=100):
        return extract_metadata_with_playwright(url)

    def download(self, item, progress_callback):
        url = item['url']
        settings = item.get('settings', {})
        output_path = self.get_download_path(settings, is_video=True)
        logging.info(f"Downloading TikTok video: {item.get('title', 'Unknown')} to {output_path}")
        # Placeholder for actual TikTok download logic
        time.sleep(1) # Simulate work
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
        url = item['url']
        settings = item.get('settings', {})
        # Pinterest can be images or videos. Assuming image for now if title/metadata suggests?
        # For safety, default to photo path if available, else video.
        # But since we don't distinguish yet, let's assume photo for Pinterest.
        output_path = self.get_download_path(settings, is_video=False)
        logging.info(f"Downloading Pinterest item: {item.get('title', 'Unknown')} to {output_path}")
        # Placeholder for actual Pinterest download logic
        time.sleep(0.5)
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
        url = item['url']
        settings = item.get('settings', {})
        output_path = self.get_download_path(settings, is_video=True)
        logging.info(f"Downloading Facebook video: {item.get('title', 'Unknown')} to {output_path}")
        time.sleep(1)
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
        url = item['url']
        settings = item.get('settings', {})
        output_path = self.get_download_path(settings, is_video=False) # Insta often photos
        logging.info(f"Downloading Instagram post: {item.get('title', 'Unknown')} to {output_path}")
        time.sleep(1)
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
