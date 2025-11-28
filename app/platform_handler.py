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
import re
import json


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

import shutil # Ensure shutil is imported

def download_with_ytdlp(url, output_path, progress_callback, settings={}):
    """
    Helper to download video using yt-dlp.
    """
    logging.info(f"Starting yt-dlp download for {url} to {output_path}")
    
    extension = settings.get('extension', 'best')
    naming_style = settings.get('naming_style', 'Original Name')
    subtitles = settings.get('subtitles', False)
    resolution = settings.get('resolution', 'Best Available')

    # Check for FFmpeg
    ffmpeg_available = shutil.which('ffmpeg') is not None
    if not ffmpeg_available:
        logging.warning("FFmpeg not found! Fallback to 'best' single file format to avoid merging.")

    # Define filename template based on naming style
    if naming_style == 'Numbered (01. Name)':
        outtmpl = f'{output_path}/%(autonumber)02d. %(title)s.%(ext)s'
    else:
        outtmpl = f'{output_path}/%(title)s.%(ext)s'

    ydl_opts = {
        'outtmpl': outtmpl,
        'progress_hooks': [lambda d: progress_callback(int(float(d.get('downloaded_bytes', 0)) / float(d.get('total_bytes', 1)) * 100)) if d['status'] == 'downloading' else None],
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True, 
    }

    # Handle Subtitles
    if subtitles:
        ydl_opts['writesubtitles'] = True

    # Handle Extensions / Format selection
    if extension in ['mp3', 'wav', 'm4a']:
        if ffmpeg_available:
            # Audio Extraction (Needs FFmpeg)
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': extension,
                'preferredquality': '192',
            }]
        else:
            # Fallback for audio without FFmpeg: just get best audio, can't convert
            logging.warning("Cannot convert to specific audio format without FFmpeg. Downloading best available audio.")
            ydl_opts['format'] = 'bestaudio/best'
            # We can't guarantee extension match here without conversion
            
    elif extension in ['mp4', 'mkv', 'webm']:
        # Video Format selection
        target_format = f'bestvideo+bestaudio/best' # Default target
        
        if not ffmpeg_available:
            # Must use single file if no FFmpeg
            target_format = 'best'

        if resolution != 'Best Available':
            res_map = { "4K": 2160, "1080p": 1080, "720p": 720, "480p": 480, "360p": 360 }
            height = res_map.get(resolution)
            if height:
                if ffmpeg_available:
                    ydl_opts['format'] = f'bestvideo[height<={height}]+bestaudio/best[height<={height}]'
                else:
                    ydl_opts['format'] = f'best[height<={height}]'
            else:
                ydl_opts['format'] = target_format
        else:
            ydl_opts['format'] = target_format
            
        # Merge output format requires FFmpeg usually, unless we are just renaming
        if ffmpeg_available:
            ydl_opts['merge_output_format'] = extension
            
    elif extension in ['jpg', 'png']:
         ydl_opts['writethumbnail'] = True
         ydl_opts['skip_download'] = True 
    else:
        # Best available
        if ffmpeg_available:
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
        else:
            ydl_opts['format'] = 'best'
    
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

import json

def extract_pinterest_direct_url(url):
    """
    Uses Playwright to extract the direct video URL from Pinterest.
    Strategy:
    1. Intercept network requests (m3u8/mp4).
    2. Parse the __PWS_DATA__ JSON blob (most reliable).
    3. Inspect DOM for <video> tags.
    4. Regex scan page content.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None
        
    video_url = None
    
    def handle_response(response):
        nonlocal video_url
        if video_url: return
        if response.request.resource_type == "media" or '.m3u8' in response.url or '.mp4' in response.url:
             if 'pinimg.com' in response.url and ('.m3u8' in response.url or '.mp4' in response.url):
                 video_url = response.url

    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as e:
                logging.error(f"Error launching browser: {e}")
                return None

            # Use a mobile user agent to potentially get a simpler page structure
            # but desktop often has the full JSON data. Let's stick to a modern desktop UA.
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.199 Safari/537.36")
            page = context.new_page()
            page.on("response", handle_response)
            
            logging.info(f"Playwright fallback scraping for: {url}")
            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
            except Exception:
                pass 

            # Strategy 1: Check if network intercept caught it immediately
            start_time = time.time()
            while not video_url and time.time() - start_time < 3:
                page.wait_for_timeout(500)
            
            if video_url:
                browser.close()
                return video_url

            # Strategy 2: Parse __PWS_DATA__ JSON
            try:
                # Get the script content
                json_data = page.evaluate("""
                    () => {
                        const script = document.getElementById('__PWS_DATA__');
                        return script ? script.innerText : null;
                    }
                """)
                
                if json_data:
                    data = json.loads(json_data)
                    # Traverse JSON to find video URL
                    # Structure varies, need to search recursively or check known paths
                    
                    def find_video_url(obj):
                        if isinstance(obj, dict):
                            if 'video_list' in obj:
                                v_list = obj['video_list']
                                # Prefer higher quality
                                if 'V_720P' in v_list: return v_list['V_720P']['url']
                                if 'V_EXP7' in v_list: return v_list['V_EXP7']['url']
                                if 'V_HLSV3_MOBILE' in v_list: return v_list['V_HLSV3_MOBILE']['url']
                                # Return first available
                                for k, v in v_list.items():
                                    if 'url' in v: return v['url']
                            
                            for key, value in obj.items():
                                res = find_video_url(value)
                                if res: return res
                        elif isinstance(obj, list):
                            for item in obj:
                                res = find_video_url(item)
                                if res: return res
                        return None

                    extracted_url = find_video_url(data)
                    if extracted_url:
                        # Sometimes it's an .m3u8, sometimes .mp4
                        logging.info(f"Found video URL in JSON: {extracted_url}")
                        browser.close()
                        return extracted_url
            except Exception as e:
                logging.warning(f"JSON parsing failed: {e}")

            # Strategy 3: Check DOM for video tag
            try:
                page.evaluate("() => { const v = document.querySelector('video'); if(v) v.play(); }")
                time.sleep(2)
                
                if video_url:
                    browser.close()
                    return video_url
                    
                src = page.evaluate("() => { const v = document.querySelector('video'); return v ? v.src : null; }")
                if src and src.startswith('http') and ('pinimg.com' in src or 'pinterest' in src):
                    browser.close()
                    return src
            except Exception:
                pass

            # Strategy 4: Regex search in page content (Last resort)
            content = page.content()
            m3u8_matches = re.findall(r'(https?://[^"]+pinimg[^"]+\.m3u8)', content)
            if m3u8_matches:
                browser.close()
                return m3u8_matches[0]
            
            mp4_matches = re.findall(r'(https?://[^"]+pinimg[^"]+\.mp4)', content)
            if mp4_matches:
                browser.close()
                return mp4_matches[0]

            browser.close()
    except Exception as e:
        logging.error(f"Playwright fallback error: {e}")
        return None
        
    return video_url

def extract_pinterest_image_url(url):
    """
    Uses Playwright to extract the high-res image URL from Pinterest.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None
    
    image_url = None
    
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as e:
                logging.error(f"Error launching browser: {e}")
                return None

            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.199 Safari/537.36")
            page = context.new_page()
            
            logging.info(f"Playwright image scraping for: {url}")
            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
            except Exception:
                pass 

            # Strategy 1: Parse __PWS_DATA__ JSON
            try:
                json_data = page.evaluate("""
                    () => {
                        const script = document.getElementById('__PWS_DATA__');
                        return script ? script.innerText : null;
                    }
                """)
                
                if json_data:
                    data = json.loads(json_data)
                    
                    def find_image_url(obj):
                        if isinstance(obj, dict):
                            if 'images' in obj and isinstance(obj['images'], dict):
                                imgs = obj['images']
                                if 'orig' in imgs and 'url' in imgs['orig']:
                                    return imgs['orig']['url']
                                if 'large' in imgs and 'url' in imgs['large']:
                                    return imgs['large']['url']
                            
                            for key, value in obj.items():
                                res = find_image_url(value)
                                if res: return res
                        elif isinstance(obj, list):
                            for item in obj:
                                res = find_image_url(item)
                                if res: return res
                        return None

                    extracted_url = find_image_url(data)
                    if extracted_url:
                        logging.info(f"Found image URL in JSON: {extracted_url}")
                        image_url = extracted_url
            except Exception as e:
                logging.warning(f"JSON parsing for image failed: {e}")

            # Strategy 2: Check DOM for main image
            if not image_url:
                try:
                    # Look for the main image (often has specific classes or is the largest)
                    # Simple heuristic: finding the image inside the pin wrapper
                    src = page.evaluate("""
                        () => {
                            // Try to find the structured data image first
                            const metaImg = document.querySelector('meta[property="og:image"]');
                            if (metaImg) return metaImg.content;
                            
                            // Fallback to finding the largest image
                            const imgs = Array.from(document.querySelectorAll('img'));
                            if (imgs.length === 0) return null;
                            
                            // Sort by area
                            imgs.sort((a, b) => (b.width * b.height) - (a.width * a.height));
                            return imgs[0].src;
                        }
                    """)
                    if src:
                        image_url = src
                except Exception:
                    pass

            browser.close()
    except Exception as e:
        logging.error(f"Playwright image fallback error: {e}")
        return None
        
    return image_url

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
            # 1. Try Standard yt-dlp
            # Note: yt-dlp might fail for simple images, so we consider failure as "try next method"
            if download_with_ytdlp(url, output_path, progress_callback, settings):
                return True
            
            # 2. Fallback: Extract direct video URL
            logging.info(f"Standard download failed for {url}. Attempting fallback extraction...")
            direct_url = extract_pinterest_direct_url(url)
            
            if direct_url:
                logging.info(f"Found direct video URL: {direct_url}")
                # Use yt-dlp on the direct URL (it handles headers/streams better than urllib)
                return download_with_ytdlp(direct_url, output_path, progress_callback, settings)
            
            # 3. Fallback: Extract direct Image URL (New Logic)
            logging.info(f"Video extraction failed for {url}. Checking for image...")
            image_url = extract_pinterest_image_url(url)
            
            if image_url:
                logging.info(f"Found direct image URL: {image_url}")
                # Update output path for image (since we defaulted to video path above)
                output_path = self.get_download_path(settings, is_video=False)
                return download_direct(image_url, output_path, title, progress_callback)
            else:
                logging.error("Fallback extraction failed.")
                return False

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