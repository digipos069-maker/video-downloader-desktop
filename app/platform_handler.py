"""
Platform-specific handlers for scraping and downloading.
Now utilizing Playwright for robust metadata extraction.
"""
import yt_dlp
from abc import ABC, abstractmethod
import time
from urllib.parse import urlparse
import logging
import os
import urllib.request


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

def is_valid_media_link(href, domain):
    """
    Determines if a link is a valid media (image/video) URL based on extension or platform patterns.
    """
    # 1. Check for direct media file extensions
    media_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.mkv', '.avi', '.mov', '.webm')
    if href.lower().endswith(media_extensions):
        return True
    
    # 2. Platform-specific content patterns
    if 'youtube.com' in domain or 'youtu.be' in domain:
        return 'watch?v=' in href or 'shorts/' in href or 'youtu.be/' in href
    elif 'tiktok.com' in domain:
        return '/video/' in href
    elif 'pinterest.com' in domain:
        return '/pin/' in href
    elif 'instagram.com' in domain:
        return '/p/' in href or '/reel/' in href
    elif 'facebook.com' in domain:
         return '/watch' in href or '/videos/' in href
    
    return False

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

                    # Strict Content Filtering using helper
                    if not is_valid_media_link(href, domain):
                        continue

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

def download_with_ytdlp(url, output_path, progress_callback, settings={}):
    """
    Helper to download video using yt-dlp.
    """
    logging.info(f"Starting yt-dlp download for {url} to {output_path}")
    
    file_type = settings.get('file_type', 'video')
    file_format = settings.get('file_format', 'Best Available')

    ydl_opts = {
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        'progress_hooks': [lambda d: progress_callback(int(float(d.get('downloaded_bytes', 0)) / float(d.get('total_bytes', 1)) * 100)) if d['status'] == 'downloading' else None],
        'quiet': True,
        'no_warnings': True,
    }

    if file_type == 'audio':
        ydl_opts['format'] = 'bestaudio/best'
        if file_format != 'Best Available':
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': file_format,
                'preferredquality': '192',
            }]
    else: # Video
        if file_format != 'Best Available':
             ydl_opts['format'] = f'bestvideo+bestaudio/best'
             ydl_opts['merge_output_format'] = file_format
        else:
             ydl_opts['format'] = 'bestvideo+bestaudio/best'
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        logging.info(f"Download completed: {url}")
        progress_callback(100)
        return True
    except Exception as e:
        logging.error(f"Download failed: {e}")
        return False

def download_direct(url, output_path, title, progress_callback):
    """
    Helper to download a file directly using urllib.
    """
    logging.info(f"Starting direct download for {url} to {output_path}")
    try:
        # Determine filename
        parsed = urlparse(url)
        path = parsed.path
        ext = os.path.splitext(path)[1]
        if not ext:
            ext = '.jpg' # Default to jpg if unknown for images? Or guess.
        
        # Sanitize title for filename
        safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        if not safe_title:
            safe_title = "downloaded_item"
            
        filename = f"{safe_title}{ext}"
        full_path = os.path.join(output_path, filename)
        
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        def report_hook(block_num, block_size, total_size):
            if total_size > 0:
                percent = int((block_num * block_size * 100) / total_size)
                progress_callback(min(percent, 100))

        urllib.request.urlretrieve(url, full_path, report_hook)
        logging.info(f"Direct download completed: {full_path}")
        progress_callback(100)
        return True
    except Exception as e:
        logging.error(f"Direct download failed: {e}")
        return False

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
        return download_with_ytdlp(url, output_path, progress_callback, settings)

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
        return download_with_ytdlp(url, output_path, progress_callback, settings)

class PinterestHandler(BaseHandler):
    def can_handle(self, url):
        return 'pinterest.com' in url

    def get_metadata(self, url):
        return extract_metadata_with_playwright(url)

    def get_playlist_metadata(self, url, max_entries=100):
        return extract_metadata_with_playwright(url)

    def download(self, item, progress_callback):
        url = item['url']
        title = item.get('title', 'Pinterest Download')
        settings = item.get('settings', {})
        
        # Check if it's likely an image
        is_image = url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
        output_path = self.get_download_path(settings, is_video=not is_image)
        
        if is_image:
             return download_direct(url, output_path, title, progress_callback)
        else:
            # Try yt-dlp for videos or let it handle extraction if supported
            success = download_with_ytdlp(url, output_path, progress_callback, settings)
            # If yt-dlp fails and it looks like it might be an image (but no extension), we could try direct? 
            # But for now, let's assume if yt-dlp failed, it failed.
            return success

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
        return download_with_ytdlp(url, output_path, progress_callback, settings)

class InstagramHandler(BaseHandler):
    def can_handle(self, url):
        return 'instagram.com' in url

    def get_metadata(self, url):
        return extract_metadata_with_playwright(url)

    def get_playlist_metadata(self, url, max_entries=100):
        return extract_metadata_with_playwright(url)

    def download(self, item, progress_callback):
        url = item['url']
        title = item.get('title', 'Instagram Download')
        settings = item.get('settings', {})
        
        is_image = url.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
        output_path = self.get_download_path(settings, is_video=not is_image)
        
        if is_image:
             return download_direct(url, output_path, title, progress_callback)
        else:
             return download_with_ytdlp(url, output_path, progress_callback, settings)



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