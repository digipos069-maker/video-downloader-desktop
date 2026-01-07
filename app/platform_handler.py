"""
Platform-specific handlers for scraping and downloading.
Now utilizing Playwright for robust metadata extraction.
"""
import yt_dlp
from yt_dlp.utils import DownloadError
from abc import ABC, abstractmethod
import time
from urllib.parse import urlparse
import logging
import os
import sys
import urllib.request
import re
import json
import shutil
import psutil
from app.helpers import get_app_path

# Configure logging
logging.basicConfig(
    filename=os.path.join(get_app_path(), 'debug_log.txt'),
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
        return '/p/' in href or '/reel/' in href or '/reels/' in href or '/tv/' in href
    elif 'facebook.com' in domain:
        # These are direct video/reel links and are always valid
        if '/watch' in href or '/videos/' in href or '/reel/' in href:
            return True
        # Story links are valid
        if 'story.php' in href:
            return True
        # fb.watch short links are valid
        if 'fb.watch' in href:
             return True
             
        # Exclude common non-video pages to avoid false positives from the scraper
        if any(x in href for x in ['/photo.php', '/photo/', 'sk=photos', 'sk=about', 'sk=followers', 'sk=following', 'php?id=']):
            return False
            
        # A simple path without a specific video indicator is usually a profile link, not a video
        # We allow them to be passed to the handler, but the scraper shouldn't treat them as media
        # Let the handler logic decide if it's a page to be scraped.
        # This part of the logic is tricky, so we rely on the positive indicators above.
        # If no specific video pattern is found, we assume it's not a direct media link.
        return False
    
    return False

def check_browser_process(browser_name):
    """
    Checks if the specified browser is running and raises an exception if it is.
    """
    browser_processes = {
        'chrome': ['chrome.exe', 'chrome'],
        'firefox': ['firefox.exe', 'firefox'],
        'opera': ['opera.exe', 'opera'],
        'edge': ['msedge.exe', 'msedge'],
        'brave': ['brave.exe', 'brave'],
        'vivaldi': ['vivaldi.exe', 'vivaldi']
    }
    
    target_procs = browser_processes.get(browser_name.lower(), [])
    if not target_procs:
        return

    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] in target_procs:
                raise Exception(f"Browser '{browser_name}' is open. Please close it to allow access to cookies.")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

def parse_cookie_file(cookie_file):
    """
    Parses a Netscape format cookie file into a list of dicts for Playwright.
    """
    cookies = []
    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                
                parts = line.strip().split('\t')
                if len(parts) >= 7:
                    domain = parts[0]
                    flag = parts[1] == 'TRUE'
                    path = parts[2]
                    secure = parts[3] == 'TRUE'
                    expiration = int(parts[4]) if parts[4].isdigit() else 0
                    name = parts[5]
                    value = parts[6]
                    
                    cookie = {
                        'name': name,
                        'value': value,
                        'domain': domain,
                        'path': path,
                        'expires': expiration,
                        'httpOnly': False, # Netscape doesn't specify, assume False
                        'secure': secure,
                        'sameSite': 'Lax' # Default safe bet
                    }
                    cookies.append(cookie)
    except Exception as e:
        logging.error(f"Error parsing cookie file: {e}")
    return cookies

def extract_metadata_with_playwright(url, max_entries=100, settings={}, callback=None):
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
                # Try to give a hint about the error
                if "Executable doesn't exist" in str(e):
                    logging.error("Playwright cannot find the browser. Please ensure the 'playwright-browsers' folder is in the app directory.")
                return [{'url': url, 'title': 'Error: Browser Launch Failed', 'type': 'error'}]

            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # Load Cookies if provided
            cookie_file = settings.get('cookie_file')
            if cookie_file and os.path.exists(cookie_file):
                logging.info(f"Loading cookies from: {cookie_file}")
                cookies = parse_cookie_file(cookie_file)
                if cookies:
                    try:
                        context.add_cookies(cookies)
                        logging.info(f"Added {len(cookies)} cookies to browser context.")
                    except Exception as e:
                        logging.error(f"Failed to add cookies to context: {e}")
            
            page = context.new_page()
            
            logging.info(f"Playwright visiting: {url}")
            try:
                logging.info(f"Scraping target limit (max_entries): {max_entries}")
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                
                # Scroll to fetch more content (simulate lazy loading)
                # Dynamic scroll iterations based on max_entries
                # Assume approx 20 items per scroll, but ensure at least 5 scrolls
                estimated_scrolls = max(5, int(max_entries / 20) + 2)
                logging.info(f"Starting scroll loop. Planned iterations: {estimated_scrolls} for max {max_entries} items.")

                # Center mouse to ensure scroll works on the main container
                if page.viewport_size:
                    page.mouse.move(page.viewport_size['width'] / 2, page.viewport_size['height'] / 2)

                # Parse the domain to filter links
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.replace('www.', '') # Remove www for broader matching
                
                unique_urls = set()
                all_seen_links = set() # Track all seen links to detect true stagnation
                results = []

                # Extraction function to run in browser (reusable)
                extract_func = """
                    () => {
                        const items = Array.from(document.querySelectorAll('a[href]')).map(a => {
                            let t = a.innerText;
                            
                            // Visual coordinates for sorting
                            const rect = a.getBoundingClientRect();
                            const container = a.closest('[data-test-id="pin"], .pin, .post, article, [role="link"]');

                            // Filter out generic titles like "Save"
                            const isGeneric = (str) => {
                                if (!str) return true;
                                const s = str.trim().toLowerCase();
                                return s === 'save' || s === 'visit' || s === 'share' || s === 'more' || s.includes('skip');
                            };

                            if (isGeneric(t)) {
                                t = a.getAttribute('aria-label') || a.getAttribute('title');
                            }

                            // Fallback 2: Image alt text (Common for thumbnail links)
                            if (isGeneric(t)) {
                                const img = a.querySelector('img');
                                if (img) t = img.alt;
                            }

                            // Fallback 3: Search the whole container for better text
                            if (isGeneric(t) && container) {
                                // Look for anything that isn't generic
                                const texts = Array.from(container.querySelectorAll('h1, h2, h3, [data-test-id="pin-title"], .title'))
                                    .map(el => el.innerText)
                                    .filter(txt => !isGeneric(txt));
                                if (texts.length > 0) t = texts[0];
                            }
                            
                            // Video Hint: Look for video indicators in the item's container
                            let isVideo = false;
                            if (container) {
                                if (container.querySelector('video, [aria-label*="video"], [aria-label*="Video"], .video-icon, [data-test-id*="video"]')) {
                                    isVideo = true;
                                }
                                // Duration patterns like 0:15 or 1:20
                                if (container.innerText && container.innerText.match(/\\d+:\\d+/)) {
                                    isVideo = true;
                                }
                            }

                            return {
                                url: a.href,
                                text: t,
                                top: rect.top + window.scrollY,
                                left: rect.left + window.scrollX,
                                is_video_hint: isVideo
                            };
                        });
                        
                        // Filter and Deduplicate
                        const unique = new Map();
                        items.forEach(item => {
                            if (!item.url || !item.url.startsWith('http')) return;
                            const lowText = item.text ? item.text.toLowerCase() : "";
                            if (lowText.includes('skip to content') || 
                                lowText.includes('skip to main') ||
                                lowText === 'skip') return;
                            
                            // DO NOT aggressively normalize URL here, let python handle it.
                            if (!unique.has(item.url)) {
                                unique.set(item.url, item);
                            }
                        });

                        return Array.from(unique.values()).sort((a, b) => {
                            // Sort by top (vertical), then by left (horizontal)
                            const rowDiff = a.top - b.top;
                            if (Math.abs(rowDiff) > 150) return rowDiff;
                            return a.left - b.left;
                        });
                    }
                """
                
                # Dynamic Loop
                # Use a while loop to ensure we keep scrolling until we get enough items
                # or we hit a hard limit/stagnation.
                
                iteration = 0
                max_iterations = 200 # Safety hard limit
                previous_count = 0
                stagnant_scrolls = 0
                
                logging.info(f"Starting dynamic scroll loop. Target: {max_entries} items.")
                
                while len(results) < max_entries and iteration < max_iterations:
                    iteration += 1
                    
                    # Scroll Strategy: Aggressive Mix
                    
                    # 1. Key Press (PageDown is usually most reliable for feeds)
                    page.keyboard.press("PageDown")
                    time.sleep(0.5)
                    
                    # 2. Mouse Wheel (Backup trigger)
                    page.mouse.wheel(0, 15000)
                    time.sleep(0.5)

                    # 3. End Key (Aggressive - good for infinite scrolls)
                    page.keyboard.press("End")
                    time.sleep(0.5)
                    
                    # 4. Scroll ALL potential containers (Facebook/Insta specific)
                    try:
                        page.evaluate("""
                            () => {
                                const containers = document.querySelectorAll('[role="feed"], .scrollable, [style*="overflow: auto"], [style*="overflow: scroll"], [style*="overflow-y: auto"], [style*="overflow-y: scroll"]');
                                containers.forEach(el => {
                                    el.scrollTop += 1500;
                                });
                                // Also try window scroll to bottom
                                window.scrollTo(0, document.body.scrollHeight);
                            }
                        """)
                    except Exception:
                        pass

                    # Wait for load (increased to 4s for reliability)
                    time.sleep(4.0)
                    
                    logging.debug(f"Scroll iteration {iteration} completed")
                    
                    # Incremental extraction
                    extracted_links = page.evaluate(extract_func)
                    
                    new_items_found = 0
                    raw_new_items = 0
                    
                    for link in extracted_links:
                        href = link['url']
                        text = link['text'] or "Scraped Link"
                        
                        # Track raw progress to prevent premature stagnation
                        if href not in all_seen_links:
                            all_seen_links.add(href)
                            raw_new_items += 1
                        
                        # For Facebook/Insta, DO NOT strip query params aggressively if they contain video IDs
                        if 'facebook.com' in domain:
                             clean_href = href
                        else:
                             # Normalize URL for de-duplication (strip query params)
                             clean_href = href.split('#')[0].split('?')[0].rstrip('/')
                        
                        # Basic filtering
                        if clean_href in unique_urls: continue
                        if not href.startswith('http'): continue
                        
                        # Check if link belongs to same domain (fuzzy match)
                        is_pin = 'pinterest.com/pin/' in href
                        if domain not in href and not is_pin: continue

                        # Strict Content Filtering using helper
                        if not is_valid_media_link(href, domain): 
                            logging.debug(f"Filtered out link (invalid format): {href}")
                            continue

                        unique_urls.add(clean_href)
                        item = {
                            'url': clean_href,
                            'title': text.strip() if text else "",
                            'type': 'scraped_link'
                        }
                        results.append(item)
                        if callback:
                            callback(item)

                        new_items_found += 1
                    
                    current_count = len(results)
                    logging.info(f"Loop status: Iteration {iteration}, Found {current_count}/{max_entries} items (+{new_items_found} new valid, +{raw_new_items} raw)")

                    if raw_new_items == 0:
                        stagnant_scrolls += 1
                        # If we are far from target, be more persistent
                        stagnation_limit = 10 if len(results) < max_entries * 0.8 else 6
                        if stagnant_scrolls >= stagnation_limit:
                            logging.info(f"Scroll stagnant for {stagnation_limit} iterations. Assuming end of feed.")
                            break
                        
                        # Super aggressive fallback if stuck
                        if stagnant_scrolls >= 3:
                             logging.info("Stuck. Trying random jumps...")
                             # Jump up a bit then way down to trigger 'scroll event' detection
                             page.mouse.wheel(0, -500)
                             time.sleep(0.5)
                             page.keyboard.press("End")
                             time.sleep(1)
                    else:
                        stagnant_scrolls = 0
                
                logging.info(f"Scraping loop finished. Found {len(results)} items.")
                
                logging.info(f"Scraping found {len(results)} unique valid links.")

                if not results:
                    # Fallback: try one last scrape or just return page
                    logging.warning("No links found after scraping loop. Returning page fallback.")
                    
                    # Capture debug screenshot
                    try:
                        screenshot_path = "debug_scrape_failure.png"
                        page.screenshot(path=screenshot_path)
                        logging.info(f"Saved debug screenshot to {screenshot_path}")
                    except Exception as ss_e:
                        logging.error(f"Failed to take debug screenshot: {ss_e}")

                    page_title = page.title()
                    item = {
                        'url': url,
                        'title': page_title.strip() if page_title else "",
                        'type': 'webpage' 
                    }
                    results.append(item)
                    if callback:
                        callback(item)
                
            except Exception as e:
                logging.error(f"Error processing page {url}: {e}")
                results.append({'url': url, 'title': 'Page Load Error', 'type': 'error'})
            finally:
                browser.close()
                
    except Exception as e:
        logging.error(f"Playwright script error: {e}")
        results.append({'url': url, 'title': 'Scrape System Error', 'type': 'error'})
        
    return results

def extract_metadata_with_ytdlp(url, max_entries=100, settings={}, callback=None):
    """
    Helper to extract metadata using yt-dlp (better for playlists/profiles).
    """
    logging.info(f"Attempting metadata extraction with yt-dlp for: {url}")
    results = []
    try:
        ydl_opts = {
            'extract_flat': 'in_playlist', # Extract entries but don't resolve them fully if in playlist
            'playlistend': max_entries,
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
        }
        
        # Handle Cookies (Authentication)
        cookie_file = settings.get('cookie_file')
        browser_source = settings.get('cookies_from_browser')
        
        logging.debug(f"Cookie setup (metadata): File='{cookie_file}', Browser='{browser_source}'")

        if cookie_file and os.path.exists(cookie_file):
            logging.info(f"Using cookie file: {cookie_file}")
            ydl_opts['cookiefile'] = cookie_file
        elif browser_source and browser_source.lower() != 'none':
            logging.info(f"Using cookies from browser: {browser_source}")
            ydl_opts['cookiesfrombrowser'] = (browser_source, )
        else:
            logging.debug("No cookies configured for metadata extraction.")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if 'entries' in info:
                # It's a playlist/profile
                entries = info['entries']
                logging.info(f"yt-dlp found {len(entries)} entries.")
                for entry in entries:
                    # entry is a dict
                    if not entry: continue
                    
                    entry_url = entry.get('url') or entry.get('webpage_url')
                    title = entry.get('title', '')
                    
                    # Construct for specific platforms if needed
                    if not entry_url:
                         if 'id' in entry and 'ie_key' in entry:
                             if entry['ie_key'] == 'TikTok':
                                 entry_url = f"https://www.tiktok.com/@{entry.get('uploader_id', 'user')}/video/{entry['id']}"
                             elif entry['ie_key'] == 'Youtube':
                                 entry_url = f"https://www.youtube.com/watch?v={entry['id']}"
                    
                    if entry_url:
                        item = {
                            'url': entry_url,
                            'title': title,
                            'type': 'video'
                        }
                        results.append(item)
                        if callback:
                            callback(item)
            else:
                # It's a single video
                logging.info("yt-dlp found single video.")
                item = {
                    'url': info.get('webpage_url', url),
                    'title': info.get('title', ''),
                    'type': 'video'
                }
                results.append(item)
                if callback:
                    callback(item)

    except Exception as e:
        logging.error(f"yt-dlp metadata extraction failed: {e}")
        # Fallback to playwright
        return extract_metadata_with_playwright(url, max_entries, settings=settings, callback=callback)
        
    if not results:
         logging.warning("yt-dlp returned no results, falling back to playwright.")
         return extract_metadata_with_playwright(url, max_entries, settings=settings, callback=callback)

    return results

class SafeYoutubeDL(yt_dlp.YoutubeDL):
    """
    Subclass of YoutubeDL to enforce stricter filename sanitization for Windows/OneDrive.
    """
    def prepare_filename(self, info_dict, *args, **kwargs):
        try:
            # Pass all arguments to the superclass method
            original_path = super().prepare_filename(info_dict, *args, **kwargs)
        except Exception as e:
            logging.warning(f"SafeYoutubeDL: super().prepare_filename failed: {e}. Using fallback.")
            # Fallback: simple Title.ext
            filename = f"{info_dict.get('title', 'video')}.{info_dict.get('ext', 'mp4')}"
            # Try to find output directory from params
            outtmpl = self.params.get('outtmpl', {})
            if isinstance(outtmpl, dict):
                template = outtmpl.get('default', '.')
            else:
                template = outtmpl
            directory = os.path.dirname(template) if template else '.'
            original_path = os.path.join(directory, filename)
        
        # Split into directory and filename
        directory, filename = os.path.split(original_path)
        
        # Sanitize filename
        # 1. Replace Full-width Pipe (｜) and standard pipe (|) with dash
        filename = filename.replace('｜', '-').replace('|', '-')
        
        # 2. Strip other potentially dangerous characters for Windows/OneDrive
        # < > : " / \ | ? *
        filename = re.sub(r'[<>:"/\\|?*]', '-', filename)
        
        # 3. Trim whitespace
        filename = filename.strip()
        
        # 4. Ensure it doesn't end with a dot (Windows issue)
        if filename.endswith('.'):
            filename = filename[:-1]
            
        return os.path.join(directory, filename)

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
    ffmpeg_available = False
    ffmpeg_location = None
    
    # Priority 1: Check in the same directory as the executable (Frozen app / PyInstaller)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        bundled_ffmpeg = os.path.join(exe_dir, 'ffmpeg.exe')
        if os.path.exists(bundled_ffmpeg):
            ffmpeg_location = bundled_ffmpeg
            ffmpeg_available = True
            logging.info(f"Found bundled FFmpeg at: {ffmpeg_location}")
        else:
            # Check _internal for one-dir mode if not in root
            internal_ffmpeg = os.path.join(exe_dir, '_internal', 'ffmpeg.exe')
            if os.path.exists(internal_ffmpeg):
                ffmpeg_location = internal_ffmpeg
                ffmpeg_available = True
                logging.info(f"Found bundled FFmpeg at: {ffmpeg_location}")

    # Priority 2: Check in project/current directory (Dev / Fallback)
    if not ffmpeg_available:
        cwd_ffmpeg = os.path.join(os.getcwd(), 'ffmpeg.exe')
        # Also check app directory if different
        app_dir_ffmpeg = os.path.join(get_app_path(), 'ffmpeg.exe')
        
        if os.path.exists(cwd_ffmpeg):
            ffmpeg_location = cwd_ffmpeg
            ffmpeg_available = True
            logging.info(f"Found CWD FFmpeg at: {ffmpeg_location}")
        elif os.path.exists(app_dir_ffmpeg):
            ffmpeg_location = app_dir_ffmpeg
            ffmpeg_available = True
            logging.info(f"Found App Dir FFmpeg at: {ffmpeg_location}")

    # Priority 3: System PATH
    if not ffmpeg_available:
        if shutil.which('ffmpeg'):
            ffmpeg_available = True
            logging.info("FFmpeg found in system PATH.")
        else:
            logging.warning("FFmpeg NOT found in bundled dir, CWD, or PATH.")

    if not ffmpeg_available:
        logging.warning(f"FFmpeg not found. Fallback to 'best' single file format to avoid merging.")

    # Define filename template based on naming style
    if settings.get('forced_filename'):
        # Platform specific override to ensure uniqueness (e.g. Pinterest)
        outtmpl = f"{output_path}/{settings['forced_filename']}.%(ext)s"
    elif naming_style == 'Numbered (01. Name)':
        outtmpl = f'{output_path}/%(autonumber)02d. %(title)s.%(ext)s'
    elif naming_style == 'Video + Caption (.txt)':
        # Add ID to prevent collisions which cause rename errors on Windows (WinError 32)
        # especially when concurrent downloads share the same generic title like "Video"
        outtmpl = f'{output_path}/%(title)s_%(id)s.%(ext)s'
    else:
        # Original Name
        outtmpl = f'{output_path}/%(title)s.%(ext)s'

    def ydl_progress_hook(d):
        if d['status'] == 'downloading':
            try:
                total = d.get('total_bytes')
                if total is None:
                    total = d.get('total_bytes_estimate')
                
                downloaded = d.get('downloaded_bytes', 0)
                
                if total and total > 0:
                    percent = (downloaded / total) * 100
                else:
                    percent = 0
                
                # Clamp between 0 and 100 and ensure integer
                safe_percent = max(0, min(100, int(percent)))
                progress_callback(safe_percent)
            except Exception as e:
                logging.error(f"Progress calculation error: {e}")

    ydl_opts = {
        'outtmpl': outtmpl,
        'progress_hooks': [ydl_progress_hook],
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'overwrites': True, # Force overwrite to prevent WinError 32 on rename
        'restrictfilenames': False, # We handle sanitization manually in SafeYoutubeDL
        'windowsfilenames': True,   # Enforce Windows-compatible filenames
    }
    
    if ffmpeg_location:
        ydl_opts['ffmpeg_location'] = ffmpeg_location

    # Handle Subtitles
    if subtitles:
        ydl_opts['writesubtitles'] = True
        
    # Handle Cookies (Authentication)
    cookie_file = settings.get('cookie_file')
    browser_source = settings.get('cookies_from_browser')
    
    logging.debug(f"Cookie setup (download): File='{cookie_file}', Browser='{browser_source}'")

    if cookie_file and os.path.exists(cookie_file):
        logging.info(f"Using cookie file: {cookie_file}")
        ydl_opts['cookiefile'] = cookie_file
    elif browser_source and browser_source.lower() != 'none':
        logging.info(f"Using cookies from browser: {browser_source}")
        check_browser_process(browser_source) # Check if browser is open
        ydl_opts['cookiesfrombrowser'] = (browser_source, )
    else:
        logging.debug("No cookies configured for download.")

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
        # Use SafeYoutubeDL subclass for stricter filename sanitization
        with SafeYoutubeDL(ydl_opts) as ydl:
            # Use extract_info with download=True to get metadata AND download
            try:
                info = ydl.extract_info(url, download=True)
            except DownloadError as e:
                if "Could not copy Chrome cookie database" in str(e):
                    raise Exception("Please close Chrome to allow cookie access, or use 'Cookies File' option.")
                else:
                    raise e # Re-raise other download errors
            
            # Handle Caption (.txt) generation
            if naming_style == 'Video + Caption (.txt)':
                try:
                    # Determine final filename
                    if 'requested_downloads' in info:
                        # Multiformat/merged case
                        final_filename = info['requested_downloads'][0]['filepath']
                    else:
                        # Direct single file case
                        final_filename = ydl.prepare_filename(info)
                    
                    # Change extension to .txt
                    base_name = os.path.splitext(final_filename)[0]
                    txt_filename = f"{base_name}.txt"
                    
                    # Content: Title + Description
                    title = info.get('title', '')
                    desc = info.get('description', '')
                    
                    content = f"{title}\n\n{desc}"
                    
                    with open(txt_filename, 'w', encoding='utf-8') as f:
                        f.write(content)
                        
                    logging.info(f"Caption saved to: {txt_filename}")
                except Exception as e:
                    logging.error(f"Failed to save caption: {e}")

        logging.info(f"Download completed: {url}")
        progress_callback(100)
        return True
    except Exception as e:
        import traceback
        logging.error(f"Download failed detailed: {traceback.format_exc()}")
        msg = str(e)
        # Check if we should suppress specific expected errors (e.g. Pinterest images)
        is_expected_error = "No video formats found" in msg or "Requested format is not available" in msg
        
        if settings.get('suppress_expected_errors') and is_expected_error:
             logging.info(f"yt-dlp did not find video (likely an image/mixed content): {msg}")
        else:
             logging.error(f"Download failed: {e}")
             
        # Re-raise to allow worker to capture the specific message
        if "Please close Chrome" in msg:
            raise e 
        return False

def download_direct(url, output_path, title, progress_callback, settings={}):
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
        
        # Handle Caption (.txt) generation
        naming_style = settings.get('naming_style', 'Original Name')
        if naming_style == 'Video + Caption (.txt)':
            try:
                base_name = os.path.splitext(full_path)[0]
                txt_filename = f"{base_name}.txt"
                with open(txt_filename, 'w', encoding='utf-8') as f:
                    f.write(title) # Direct downloads (images) usually only have title passed
                logging.info(f"Caption saved to: {txt_filename}")
            except Exception as e:
                logging.error(f"Failed to save caption for direct download: {e}")

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
                if "Executable doesn't exist" in str(e):
                    logging.error("Playwright cannot find the browser. Please ensure the 'playwright-browsers' folder is in the app directory.")
                return None

            # Use a mobile user agent to potentially get a simpler page structure
            # but desktop often has the full JSON data. Let's stick to a modern desktop UA.
            # Use a mobile user agent to potentially get a simpler page structure
            # but desktop often has the full JSON data. Let's stick to a modern desktop UA.
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
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
            m3u8_matches = re.findall(r'(https?://[^"]+pinimg[^"].m3u8)', content)
            if m3u8_matches:
                browser.close()
                return m3u8_matches[0]
            
            mp4_matches = re.findall(r'(https?://[^"]+pinimg[^"].mp4)', content)
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
                if "Executable doesn't exist" in str(e):
                    logging.error("Playwright cannot find the browser. Please ensure the 'playwright-browsers' folder is in the app directory.")
                return None

            # Use a mobile user agent to potentially get a simpler page structure
            # but desktop often has the full JSON data. Let's stick to a modern desktop UA.
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
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
    def get_playlist_metadata(self, url, max_entries=100, settings={}, callback=None):
        pass

    @abstractmethod
    def download(self, item, progress_callback):
        pass

    def get_download_path(self, settings, is_video=True, item_url=None):
        """Helper to determine the download path from settings."""
        base_path = settings.get('video_path') if is_video else settings.get('photo_path')
        if not base_path:
             base_path = settings.get('photo_path') if is_video else settings.get('video_path')
        if not base_path:
             base_path = '.'
             
        # Check if we should create a subfolder based on origin
        origin_url = settings.get('origin_url')
        if origin_url and item_url:
            # Normalize URLs for comparison (strip trailing slashes)
            norm_origin = origin_url.rstrip('/')
            norm_item = item_url.rstrip('/')
            
            # Only create folder if origin is different (i.e. it's a collection/profile scrape)
            if norm_origin != norm_item:
                from urllib.parse import urlparse
                import re
                
                try:
                    parsed = urlparse(norm_origin)
                    path = parsed.path.strip('/')
                    
                    # If path is empty or just 'watch' (common for YT), fallback or skip
                    # Actually, if it's different, we try to use the path.
                    # For YT playlist: /playlist?list=... -> path is 'playlist'. Not great.
                    # For TikTok: /@user -> @user. Good.
                    
                    folder_name = ""
                    
                    # Special handling for common platforms
                    query_part = ""
                    if parsed.query:
                        # Use the first query parameter
                        first_param = parsed.query.split('&')[0]
                        query_part = f"_{first_param}"

                    if 'youtube.com' in norm_origin or 'youtu.be' in norm_origin:
                        if 'playlist' in path:
                             # Use query param 'list' if possible, or just 'Playlist'
                             # We don't have easy access to query params here without parsing query
                             from urllib.parse import parse_qs
                             qs = parse_qs(parsed.query)
                             if 'list' in qs:
                                 folder_name = f"Playlist_{qs['list'][0]}"
                        elif 'channel' in path or 'c/' in path or 'user' in path or '@' in path:
                             folder_name = path.replace('/', '_') + query_part
                    elif 'tiktok.com' in norm_origin:
                        folder_name = path.replace('/', '_') + query_part
                    elif 'instagram.com' in norm_origin:
                         folder_name = path.replace('/', '_') + query_part
                    else:
                        folder_name = path.replace('/', '_') + query_part
                    
                    # Sanitize
                    if folder_name:
                        safe_name = "".join([c for c in folder_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_', '.')]).rstrip()
                        if safe_name:
                            base_path = os.path.join(base_path, safe_name)
                except Exception as e:
                    logging.error(f"Error creating folder path from origin: {e}")

        return base_path

# --- Handlers now use Playwright for Scraping ---

class YouTubeHandler(BaseHandler):
    def can_handle(self, url):
        return 'youtube.com' in url or 'youtu.be' in url

    def get_metadata(self, url):
        return extract_metadata_with_playwright(url)

    def get_playlist_metadata(self, url, max_entries=100, settings={}, callback=None):
        return extract_metadata_with_ytdlp(url, max_entries, settings, callback=callback)

    def download(self, item, progress_callback):
        url = item['url']
        settings = item.get('settings', {})
        output_path = self.get_download_path(settings, is_video=True, item_url=url)
        return download_with_ytdlp(url, output_path, progress_callback, settings)

class TikTokHandler(BaseHandler):
    def can_handle(self, url):
        return 'tiktok.com' in url

    def get_metadata(self, url):
        return extract_metadata_with_playwright(url)

    def get_playlist_metadata(self, url, max_entries=100, settings={}, callback=None):
        # Prefer yt-dlp for scraping lists on TikTok as it is more robust than raw Playwright
        return extract_metadata_with_ytdlp(url, max_entries, settings=settings, callback=callback)

    def download(self, item, progress_callback):
        url = item['url']
        settings = item.get('settings', {})
        output_path = self.get_download_path(settings, is_video=True, item_url=url)
        return download_with_ytdlp(url, output_path, progress_callback, settings)

class PinterestHandler(BaseHandler):
    def can_handle(self, url):
        return 'pinterest.com' in url

    def get_metadata(self, url):
        return extract_metadata_with_playwright(url)

    def get_playlist_metadata(self, url, max_entries=100, settings={}, callback=None):
        # Prefer Playwright for scrolling/scraping lists on Pinterest
        return extract_metadata_with_playwright(url, max_entries, settings=settings, callback=callback)

    def download(self, item, progress_callback):
        url = item['url']
        title = item.get('title', 'Pinterest Download')
        settings = item.get('settings', {})
        
        logging.debug(f"[PinterestHandler] Processing: {url} | Title: {title}")

        # EXTRACT PIN ID to ensure unique filenames
        # URL format is usually: https://pinterest.com/pin/123456789/
        try:
            pin_id = ""
            parts = url.strip('/').split('/')
            # Look for 'pin' and take the next segment
            if 'pin' in parts:
                idx = parts.index('pin')
                if idx + 1 < len(parts):
                    pin_id = parts[idx+1]
            
            # Fallback: if no 'pin' keyword, take last numeric segment
            if not pin_id:
                 for part in reversed(parts):
                     if part.isdigit():
                         pin_id = part
                         break
            
            logging.debug(f"[PinterestHandler] Extracted Pin ID: '{pin_id}'")

            if pin_id:
                # Check if title already contains ID to avoid duplication
                if pin_id not in title:
                    title = f"{title}_{pin_id}"
                    
            # Sanitize title for filename usage
            # Note: download_direct uses strictly alnum/space. We should match that robustness or rely on it.
            safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c in (' ', '_', '-')]).rstrip()
            
            if not safe_title:
                 safe_title = f"pinterest_{pin_id}" if pin_id else "pinterest_download"
            
            logging.debug(f"[PinterestHandler] Final Forced Filename: '{safe_title}'")
            
            # Pass unique filename to yt-dlp to prevent collisions
            settings['forced_filename'] = safe_title
            
        except Exception as e:
            logging.warning(f"Failed to extract Pin ID for unique filename: {e}")

        # Check if it's likely an image
        is_image = url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
        output_path = self.get_download_path(settings, is_video=not is_image, item_url=url)
        
        if is_image:
             return download_direct(url, output_path, title, progress_callback, settings)
        else:
            # 1. Try Standard yt-dlp
            # Note: yt-dlp might fail for simple images, so we consider failure as "try next method"
            # Suppress "No video formats found" errors for Pinterest as they are common for images
            settings['suppress_expected_errors'] = True 
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
                output_path = self.get_download_path(settings, is_video=False, item_url=url)
                return download_direct(image_url, output_path, title, progress_callback, settings)
            else:
                logging.error("Fallback extraction failed.")
                return False

class FacebookHandler(BaseHandler):
    def can_handle(self, url):
        # Use regex to be more specific about valid Facebook video/reel URLs
        # This handles:
        # - /videos/some_id
        # - /reel/some_id
        # - /watch/?v=some_id
        # - fb.watch/shortlink
        # - /story.php?story_fbid=...
        # - profile/page URLs with sk=videos or sk=reels_tab for scraping
        pattern = re.compile(
            r'facebook\.com/(?:video\.php\?v=|watch/?\?v=|reel/|story\.php\?story_fbid=|[^/]+/videos/|[^/]+/reels/)|fb\.watch/'
        )
        # Also allow profile pages that are specifically for videos/reels to be handled for scraping
        if 'sk=videos' in url or 'sk=reels_tab' in url:
            return True
            
        return pattern.search(url) is not None

    def get_metadata(self, url):
        # Prefer Playwright for Facebook metadata as yt-dlp often fails on profiles/reels
        return extract_metadata_with_playwright(url)
    
    def get_playlist_metadata(self, url, max_entries=100, settings={}, callback=None):
        # Prefer Playwright for scrolling/scraping lists on Facebook
        return extract_metadata_with_playwright(url, max_entries, settings=settings, callback=callback)

    def download(self, item, progress_callback):
        url = item['url']
        settings = item.get('settings', {})
        output_path = self.get_download_path(settings, is_video=True, item_url=url)
        return download_with_ytdlp(url, output_path, progress_callback, settings)

class InstagramHandler(BaseHandler):
    def can_handle(self, url):
        return 'instagram.com' in url

    def get_metadata(self, url):
        return extract_metadata_with_playwright(url)

    def get_playlist_metadata(self, url, max_entries=100, settings={}, callback=None):
        # Prefer Playwright for scrolling/scraping lists on Instagram
        return extract_metadata_with_playwright(url, max_entries, settings=settings, callback=callback)

    def download(self, item, progress_callback):
        url = item['url']
        title = item.get('title', 'Instagram Download')
        settings = item.get('settings', {})
        
        is_image = url.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
        output_path = self.get_download_path(settings, is_video=not is_image, item_url=url)
        
        if is_image:
             return download_direct(url, output_path, title, progress_callback, settings)
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