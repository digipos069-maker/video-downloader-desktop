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
import subprocess
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
    media_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.mkv', '.avi', '.mov', '.webm')
    if href.lower().endswith(media_extensions): return True
    if 'youtube.com' in domain or 'youtu.be' in domain:
        return 'watch?v=' in href or 'shorts/' in href or 'youtu.be/' in href
    elif 'tiktok.com' in domain:
        return '/video/' in href
    elif 'pinterest.com' in domain:
        return bool(re.search(r'/pin/\d+(?:/|\?|$)', href)) and not re.search(r'/pin/\d+/.+', href)
    elif 'instagram.com' in domain:
        return '/p/' in href or '/reel/' in href or '/reels/' in href or '/tv/' in href
    elif 'facebook.com' in domain:
        if '/watch' in href or '/videos/' in href or '/reel/' in href: return True
        if 'story.php' in href: return True
        if 'fb.watch' in href: return True
        return False
    elif 'kuaishou.com' in domain or 'kwai.com' in domain:
        return True
    elif 'reelshort.com' in domain:
        return '/episodes/' in href or '/full-episodes/' in href
    elif 'dramaboxdb.com' in domain:
        return '/ep/' in href or '/movie/' in href
    return False

def check_browser_process(browser_name):
    browser_processes = {
        'chrome': ['chrome.exe', 'chrome'],
        'firefox': ['firefox.exe', 'firefox'],
        'opera': ['opera.exe', 'opera'],
        'edge': ['msedge.exe', 'msedge'],
        'brave': ['brave.exe', 'brave'],
        'vivaldi': ['vivaldi.exe', 'vivaldi']
    }
    target_procs = browser_processes.get(browser_name.lower(), [])
    if not target_procs: return
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] in target_procs:
                raise Exception(f"Browser '{browser_name}' is open. Please close it to allow access to cookies.")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess): pass

def parse_cookie_file(cookie_file):
    cookies = []
    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('#') or not line.strip(): continue
                parts = line.strip().split('\t')
                if len(parts) >= 7:
                    cookie = {
                        'name': parts[5],
                        'value': parts[6],
                        'domain': parts[0],
                        'path': parts[2],
                        'expires': int(parts[4]) if parts[4].isdigit() else 0,
                        'httpOnly': False,
                        'secure': parts[3] == 'TRUE',
                        'sameSite': 'Lax'
                    }
                    cookies.append(cookie)
    except Exception as e:
        logging.error(f"Error parsing cookie file: {e}")
    return cookies

def extract_metadata_with_playwright(url, max_entries=100, settings={}, callback=None):
    if not PLAYWRIGHT_AVAILABLE:
        return [{'url': url, 'title': 'Error: Playwright Missing', 'type': 'error'}]

    results = []
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as e:
                logging.error(f"Error launching browser: {e}")
                return [{'url': url, 'title': 'Error: Browser Launch Failed', 'type': 'error'}]

            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            cookie_file = settings.get('cookie_file')
            if cookie_file and os.path.exists(cookie_file):
                cookies = parse_cookie_file(cookie_file)
                if cookies: context.add_cookies(cookies)
            
            page = context.new_page()
            
            visit_url = url
            reelshort_page = 1
            base_rs_url = url.rstrip('/')
            if 'reelshort.com' in url and re.search(r'/\d+$', base_rs_url):
                base_rs_url = base_rs_url.rsplit('/', 1)[0]

            logging.info(f"Playwright visiting: {url}")
            
            unique_urls = set()
            all_seen_links = set()
            results = []

            while True:
                items_before_page = len(results)
                try:
                    logging.info(f"Scraping page: {visit_url} (Target: {max_entries})")
                    page.goto(visit_url, timeout=60000, wait_until="domcontentloaded")
                    
                    page_title = "Main Item"
                    if 'reelshort.com' in visit_url:
                        try:
                            xpath_selector = 'xpath=//*[@id="__next"]/main/div[6]/div/div/div[2]/div[1]/div/h2'
                            element = page.wait_for_selector(xpath_selector, timeout=5000)
                            if element:
                                extracted_text = element.inner_text()
                                if extracted_text:
                                    page_title = extracted_text.strip()
                        except Exception: pass
                    
                    if page_title == "Main Item":
                        try: page_title = page.title() or "Main Item"
                        except Exception: pass

                    parsed_url = urlparse(visit_url)
                    domain = parsed_url.netloc.replace('www.', '') 
                    
                    # --- Explicitly Add Main URL if it's a direct item ---
                    if is_valid_media_link(visit_url, domain):
                        # ReelShort Exception: Don't add 'full-episodes' (series pages) as items, only actual episodes
                        if 'reelshort.com' in domain and '/full-episodes/' in visit_url:
                            pass # Skip adding series page
                        else:
                            clean_main = visit_url.split('#')[0].split('?')[0].rstrip('/')
                            if clean_main not in unique_urls:
                                item = {'url': visit_url, 'title': page_title, 'type': 'scraped_link'}
                                unique_urls.add(clean_main)
                                results.append(item)
                                if callback: callback(item)

                    extract_func = r"""
                        () => {
                            // Define isGeneric at top level scope
                            const isGeneric = (str) => {
                                if (!str) return true;
                                const s = str.trim().toLowerCase();
                                return s === 'save' || s === 'visit' || s === 'share' || s === 'more' || s.includes('skip') || s.includes('skip to');
                            };

                            const items = Array.from(document.querySelectorAll('a[href]')).map(a => {
                                let t = a.innerText;
                                const rect = a.getBoundingClientRect();
                                const container = a.closest('[data-test-id="pin"], .pin, .post, article, [role="link"]');

                                if (isGeneric(t)) t = a.getAttribute('aria-label') || a.getAttribute('title');
                                if (isGeneric(t)) { const img = a.querySelector('img'); if (img) t = img.alt; }
                                if (isGeneric(t) && container) {
                                    const texts = Array.from(container.querySelectorAll('h1, h2, h3, [data-test-id="pin-title"], .title, .video-title, .episode-name'))
                                        .map(el => el.innerText).filter(txt => !isGeneric(txt));
                                    if (texts.length > 0) t = texts[0];
                                }
                                // ReelShort Specific: Force title extraction from Episode links
                                if (window.location.host.includes('reelshort.com') && a.href.includes('/episodes/')) {
                                    // Structure: <h2 class="line-clamp-2..."><a ...>Title</a></h2>
                                    // Check if parent has the specific class
                                    if (a.parentElement && a.parentElement.classList.contains('line-clamp-2')) {
                                        t = a.innerText.trim();
                                    } 
                                    // Fallback: Check inside link or container (previous logic)
                                    else {
                                        let specificTitleEl = a.querySelector('.line-clamp-2');
                                        if (!specificTitleEl && container) {
                                            specificTitleEl = container.querySelector('.line-clamp-2');
                                        }
                                        if (specificTitleEl) {
                                            t = specificTitleEl.innerText.trim();
                                        }
                                    }
                                    
                                    // Final safety: simple text
                                    if (!t || t === '') {
                                        const rawText = a.innerText;
                                        if (rawText && rawText.trim() !== '') t = rawText.trim();
                                    }
                                }
                                let isVideo = false;
                                if (container) {
                                    if (container.querySelector('video, [aria-label*="video"], [aria-label*="Video"], .video-icon, [data-test-id*="video"]')) isVideo = true;
                                    if (container.innerText && container.innerText.match(/\d+:\d+/)) isVideo = true;
                                }
                                return {
                                    url: a.href, text: t, top: rect.top + window.scrollY, left: rect.left + window.scrollX, is_video_hint: isVideo
                                };
                            });
                            // Filter and Deduplicate (with Title Improvement)
                            const unique = new Map();
                            items.forEach(item => {
                                if (!item.url || !item.url.startsWith('http')) return;
                                
                                if (!unique.has(item.url)) {
                                    unique.set(item.url, item);
                                } else {
                                    // Check if we can improve the title
                                    const existing = unique.get(item.url);
                                    const existingIsGeneric = !existing.text || existing.text.trim() === '' || isGeneric(existing.text) || existing.text === 'Scraped Link';
                                    const newIsGood = item.text && item.text.trim() !== '' && !isGeneric(item.text);
                                    
                                    if (existingIsGeneric && newIsGood) {
                                        unique.set(item.url, item);
                                    }
                                }
                            });
                            return Array.from(unique.values()).sort((a, b) => {
                                const rowDiff = a.top - b.top;
                                if (Math.abs(rowDiff) > 250) return rowDiff;
                                return a.left - b.left;
                            });
                        }
                    """
                    
                    req_video = settings.get('video_enabled', True) 
                    req_photo = settings.get('photo_enabled', True)
                    
                    if 'pinterest.com' in domain:
                        time.sleep(3.0)
                        try:
                            ss_path = os.path.join(get_app_path(), "debug_pinterest_after_3s_load.png")
                            page.screenshot(path=ss_path)
                        except Exception: pass

                    try:
                        initial_links = page.evaluate(extract_func)
                        for link in initial_links:
                            href = link['url']
                            text = link['text'] or "Scraped Link"
                            if href not in all_seen_links: all_seen_links.add(href)
                            clean_href = href.split('#')[0].split('?')[0].rstrip('/')
                            if clean_href in unique_urls: continue
                            if not is_valid_media_link(href, domain): continue
                            is_likely_video = False
                            is_likely_photo = False
                            if 'pinterest.com' in domain:
                                if link.get('is_video_hint', False): is_likely_video = True
                                else: is_likely_photo = True
                            elif any(x in domain for x in ['youtube', 'tiktok', 'facebook', 'kuaishou', 'kwai', 'reelshort']): is_likely_video = True
                            elif 'instagram.com' in domain:
                                 if '/reel/' in href or '/reels/' in href or '/tv/' in href: is_likely_video = True
                                 elif '/p/' in href: is_likely_photo = True
                            else:
                                 if href.lower().endswith(('.mp4', '.mov', '.avi')): is_likely_video = True
                                 else: is_likely_photo = True
                            if is_likely_video and not req_video: continue
                            # ReelShort: Filter out pagination/series pages from results, keep only episodes
                            # We want /episodes/ (videos), NOT /full-episodes/ (series/pagination)
                            if 'reelshort.com' in domain and ('/full-episodes/' in clean_href or clean_href.rstrip('/').split('/')[-1].isdigit()):
                                continue

                            unique_urls.add(clean_href)
                            item = {'url': clean_href, 'title': text.strip(), 'type': 'scraped_link', 'is_video_hint': is_likely_video}
                            results.append(item)
                            if callback: callback(item)
                    except Exception as e: logging.error(f"Initial error: {e}")

                    if 'pinterest.com' in domain and '/pin/' in visit_url:
                        page.keyboard.press("End")
                        time.sleep(2.0)
                        page.mouse.wheel(0, 5000)
                        time.sleep(2.0)
                    
                    iteration = 0
                    stagnant_scrolls = 0
                    while len(results) < max_entries and iteration < 200:
                        iteration += 1
                        
                        # Optimization for ReelShort (Paginated, not Infinite Scroll)
                        if 'reelshort.com' in visit_url:
                            page.keyboard.press("End")
                            time.sleep(1.0)
                        else:
                            # Standard Aggressive Scroll
                            page.keyboard.press("PageDown")
                            time.sleep(0.5)
                            page.mouse.wheel(0, 15000)
                            time.sleep(0.5)
                            page.keyboard.press("End")
                            time.sleep(0.5)
                            try:
                                page.evaluate("""
                                    () => {
                                        const containers = document.querySelectorAll('[role="feed"], .scrollable, [style*="overflow: auto"], [style*="overflow: scroll"], [style*="overflow-y: auto"], [style*="overflow-y: scroll"]');
                                        containers.forEach(el => { el.scrollTop += 1500; });
                                        window.scrollTo(0, document.body.scrollHeight);
                                    }
                                """)
                            except Exception: pass
                            time.sleep(4.0)
                        
                        extracted_links = page.evaluate(extract_func)
                        raw_new_items = 0
                        for link in extracted_links:
                            href = link['url']
                            text = link['text'] or "Scraped Link"
                            if href not in all_seen_links: all_seen_links.add(href); raw_new_items += 1
                            clean_href = href.split('#')[0].split('?')[0].rstrip('/')
                            if clean_href in unique_urls: continue
                            if not is_valid_media_link(href, domain): continue
                            is_likely_video = False
                            is_likely_photo = False
                            if 'pinterest.com' in domain:
                                if link.get('is_video_hint', False): is_likely_video = True
                                else: is_likely_photo = True
                            elif any(x in domain for x in ['youtube', 'tiktok', 'facebook', 'kuaishou', 'kwai', 'reelshort']): is_likely_video = True
                            elif 'instagram.com' in domain:
                                 if '/reel/' in href or '/reels/' in href or '/tv/' in href: is_likely_video = True
                                 elif '/p/' in href: is_likely_photo = True
                            else:
                                 if href.lower().endswith(('.mp4', '.mov', '.avi')): is_likely_video = True
                                 else: is_likely_photo = True
                            if is_likely_video and not req_video: continue
                            if is_likely_photo and not req_photo: continue
                            
                            # ReelShort: Filter out pagination/series pages from results, keep only episodes
                            if 'reelshort.com' in domain and '/full-episodes/' in clean_href:
                                continue

                            unique_urls.add(clean_href)
                            item = {'url': clean_href, 'title': text.strip(), 'type': 'scraped_link', 'is_video_hint': is_likely_video}
                            results.append(item)
                            if callback: callback(item)
                        if raw_new_items == 0:
                            stagnant_scrolls += 1
                            if stagnant_scrolls >= (10 if len(results) < max_entries * 0.8 else 6): break
                            if stagnant_scrolls >= 3:
                                 page.mouse.wheel(0, -500); time.sleep(0.5); page.keyboard.press("End"); time.sleep(1)
                        else: stagnant_scrolls = 0

                    if not results and not 'reelshort.com' in visit_url:
                        try:
                            item = {'url': visit_url, 'title': page.title().strip(), 'type': 'webpage'}
                            results.append(item)
                            if callback: callback(item)
                        except Exception: pass
                    
                    if 'reelshort.com' in visit_url and '/full-episodes/' in visit_url and len(results) < max_entries:
                        if len(results) == items_before_page:
                            logging.info(f"No new items on page {reelshort_page}. Stopping.")
                            break
                        reelshort_page += 1
                        visit_url = f"{base_rs_url}/{reelshort_page}"
                        logging.info(f"Next page: {visit_url}")
                        continue
                    break 
                except Exception as e:
                    logging.error(f"Error: {e}")
                    break 
            browser.close()
    except Exception as e:
        logging.error(f"Playwright error: {e}")
        results.append({'url': url, 'title': 'Scrape Error', 'type': 'error'})
    return results

def extract_metadata_with_ytdlp(url, max_entries=100, settings={}, callback=None):
    logging.info(f"Attempting metadata extraction with yt-dlp for: {url}")
    results = []
    try:
        ydl_opts = {
            'extract_flat': 'in_playlist',
            'playlistend': max_entries,
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
        }
        cookie_file = settings.get('cookie_file')
        browser_source = settings.get('cookies_from_browser')
        if cookie_file and os.path.exists(cookie_file):
            ydl_opts['cookiefile'] = cookie_file
        elif browser_source and browser_source.lower() != 'none':
            ydl_opts['cookiesfrombrowser'] = (browser_source, )

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                for entry in info['entries']:
                    if not entry: continue
                    entry_url = entry.get('url') or entry.get('webpage_url')
                    if not entry_url:
                         if 'id' in entry and 'ie_key' in entry:
                             if entry['ie_key'] == 'TikTok':
                                 entry_url = f"https://www.tiktok.com/@{entry.get('uploader_id', 'user')}/video/{entry['id']}"
                             elif entry['ie_key'] == 'Youtube':
                                 entry_url = f"https://www.youtube.com/watch?v={entry['id']}"
                    if entry_url:
                        item = {'url': entry_url, 'title': entry.get('title', ''), 'type': 'video'}
                        results.append(item)
                        if callback: callback(item)
            else:
                item = {'url': info.get('webpage_url', url), 'title': info.get('title', ''), 'type': 'video'}
                results.append(item)
                if callback: callback(item)
    except Exception as e:
        logging.error(f"yt-dlp metadata extraction failed: {e}")
        return extract_metadata_with_playwright(url, max_entries, settings=settings, callback=callback)
    if not results: return extract_metadata_with_playwright(url, max_entries, settings=settings, callback=callback)
    return results

class SafeYoutubeDL(yt_dlp.YoutubeDL):
    def prepare_filename(self, info_dict, *args, **kwargs):
        try:
            original_path = super().prepare_filename(info_dict, *args, **kwargs)
        except Exception:
            filename = f"{info_dict.get('title', 'video')}.{info_dict.get('ext', 'mp4')}"
            outtmpl = self.params.get('outtmpl', {})
            directory = os.path.dirname(outtmpl.get('default', '.')) if isinstance(outtmpl, dict) else os.path.dirname(outtmpl)
            original_path = os.path.join(directory if directory else '.', filename)
        directory, filename = os.path.split(original_path)
        filename = filename.replace('｜', '-')
        filename = filename.replace('|', '-')
        filename = re.sub(r'[<>:"/\\|?*]', '-', filename).strip()
        MAX_FILENAME_LENGTH = 100
        name_part, ext = os.path.splitext(filename)
        if len(name_part) > MAX_FILENAME_LENGTH: filename = name_part[:MAX_FILENAME_LENGTH] + ext
        if filename.endswith('.'): filename = filename[:-1]
        return os.path.join(directory, filename)

class YtDlpLogger:
    def __init__(self): self.skipped = False
    def debug(self, msg):
        if "[download] " in msg and "has already been downloaded" in msg: self.skipped = True
    def warning(self, msg): pass
    def error(self, msg): pass
    def info(self, msg): pass

def convert_av1_to_h264(file_path, ffmpeg_location):
    try:
        if not os.path.exists(file_path) or not ffmpeg_location or not os.path.exists(ffmpeg_location): return False
        check_cmd = [ffmpeg_location, '-i', file_path]
        check_proc = subprocess.run(check_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = check_proc.stderr.decode('utf-8', errors='ignore').lower()
        if not ("video: av1" in output or "video: av01" in output): return False
        base, ext = os.path.splitext(file_path)
        temp_output = f"{base}_h264{ext}"
        cmd = [ffmpeg_location, '-y', '-i', file_path, '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-c:a', 'aac', temp_output]
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode == 0:
            time.sleep(0.5)
            try: os.replace(temp_output, file_path)
            except OSError:
                if os.path.exists(file_path): os.remove(file_path)
                os.rename(temp_output, file_path)
            return True
        return False
    except Exception: return False

def download_with_ytdlp(url, output_path, progress_callback, settings={}):
    extension = settings.get('extension', 'best')
    naming_style = settings.get('naming_style', 'Original Name')
    resolution = settings.get('resolution', 'Best Available')
    ffmpeg_location = None
    ffmpeg_available = False
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        bundled_ffmpeg = os.path.join(exe_dir, 'ffmpeg.exe')
        if os.path.exists(bundled_ffmpeg): ffmpeg_location = bundled_ffmpeg; ffmpeg_available = True
    if not ffmpeg_available:
        cwd_ffmpeg = os.path.join(os.getcwd(), 'ffmpeg.exe')
        app_dir_ffmpeg = os.path.join(get_app_path(), 'ffmpeg.exe')
        if os.path.exists(cwd_ffmpeg): ffmpeg_location = cwd_ffmpeg; ffmpeg_available = True
        elif os.path.exists(app_dir_ffmpeg): ffmpeg_location = app_dir_ffmpeg; ffmpeg_available = True
    if not ffmpeg_available and shutil.which('ffmpeg'): ffmpeg_available = True
    if settings.get('forced_filename'): outtmpl = f"{output_path}/{settings['forced_filename']}.%(ext)s"
    elif naming_style == 'Numbered (01. Name)': outtmpl = f'{output_path}/%(autonumber)02d. %(title)s.%(ext)s'
    elif naming_style == 'Video + Caption (.txt)': outtmpl = f'{output_path}/%(title)s_%(id)s.%(ext)s'
    else: outtmpl = f'{output_path}/%(title)s [%(id)s].%(ext)s'
    def ydl_progress_hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)
            if total and total > 0: progress_callback(max(0, min(100, int((downloaded / total) * 100))))
    logger = YtDlpLogger()
    ydl_opts = {'outtmpl': outtmpl, 'progress_hooks': [ydl_progress_hook], 'quiet': True, 'no_warnings': True, 'noplaylist': True, 'nooverwrites': True, 'windowsfilenames': True, 'logger': logger}
    if ffmpeg_location: ydl_opts['ffmpeg_location'] = ffmpeg_location
    cookie_file = settings.get('cookie_file'); browser_source = settings.get('cookies_from_browser')
    if cookie_file and os.path.exists(cookie_file): ydl_opts['cookiefile'] = cookie_file
    elif browser_source and browser_source.lower() != 'none': check_browser_process(browser_source); ydl_opts['cookiesfrombrowser'] = (browser_source, )
    if extension in ['mp3', 'wav', 'm4a']:
        if ffmpeg_available: ydl_opts['format'] = 'bestaudio/best'; ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': extension, 'preferredquality': '192'}]
        else: ydl_opts['format'] = 'bestaudio/best'
    elif extension in ['mp4', 'mkv', 'webm']:
        if extension == 'mp4': target_format = 'bestvideo[ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/bestvideo[vcodec^=avc]+bestaudio/bestvideo[vcodec!^=av01][vcodec!^=vp9]+bestaudio/bestvideo[vcodec!^=av01]+bestaudio/bestvideo+bestaudio/best'
        else: target_format = 'bestvideo+bestaudio/best'
        if not ffmpeg_available: target_format = 'best[ext=mp4]/best' if extension == 'mp4' else 'best'
        if resolution != 'Best Available':
            res_map = {"4K": 2160, "1080p": 1080, "720p": 720, "480p": 480, "360p": 360}
            height = res_map.get(resolution)
            if height:
                if ffmpeg_available:
                    if extension == 'mp4': target_format = f'bestvideo[ext=mp4][vcodec^=avc][height<={height}]+bestaudio[ext=m4a]/bestvideo[vcodec^=avc][height<={height}]+bestaudio/bestvideo[vcodec!^=av01][vcodec!^=vp9][height<={height}]+bestaudio/bestvideo[vcodec!^=av01][height<={height}]+bestaudio/bestvideo[height<={height}]+bestaudio/best[height<={height}]'
                    else: target_format = f'bestvideo[height<={height}]+bestaudio/best[height<={height}]'
                else: target_format = f'best[ext=mp4][height<={height}]/best[height<={height}]' if extension == 'mp4' else f'best[height<={height}]'
        ydl_opts['format'] = target_format
        if ffmpeg_available: ydl_opts['merge_output_format'] = extension
    elif extension in ['jpg', 'png']: ydl_opts['writethumbnail'] = True; ydl_opts['skip_download'] = True 
    else: ydl_opts['format'] = 'bestvideo+bestaudio/best' if ffmpeg_available else 'best'
    try:
        with SafeYoutubeDL(ydl_opts) as ydl:
            for attempt in range(2):
                try: info = ydl.extract_info(url, download=True); break
                except Exception as e:
                    if "[WinError 183]" in str(e) and attempt < 1:
                        match = re.search(r"-> '(.+?)'", str(e))
                        if match:
                            cp = match.group(1)
                            if os.path.exists(cp):
                                try: os.remove(cp)
                                except PermissionError: os.rename(cp, cp + f".trash_{int(time.time())}")
                                time.sleep(1); continue
                    raise e
            if naming_style == 'Video + Caption (.txt)':
                try:
                    ff = info['requested_downloads'][0]['filepath'] if 'requested_downloads' in info else ydl.prepare_filename(info)
                    txt_f = os.path.splitext(ff)[0] + ".txt"
                    content = info.get('title', '')
                    if settings.get('remove_links'): content = re.sub(r'https?://\S+', '', content)
                    if settings.get('remove_mentions'): content = re.sub(r'@\w+', '', content)
                    with open(txt_f, 'w', encoding='utf-8') as f: f.write(content.strip())
                except Exception: pass
        if logger.skipped: progress_callback(100); return True, "Already Downloaded"
        try:
            fp = info['requested_downloads'][0]['filepath'] if 'requested_downloads' in info else ydl.prepare_filename(info)
            if fp and os.path.exists(fp) and ffmpeg_available and ffmpeg_location: convert_av1_to_h264(fp, ffmpeg_location)
        except Exception: pass
        progress_callback(100); return True, "Completed"
    except Exception as e:
        if "Please close Chrome" in str(e): raise e
        return False, "Failed"

def download_direct(url, output_path, title, progress_callback, settings={}):
    try:
        ext = os.path.splitext(urlparse(url).path)[1] or '.jpg'
        safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).strip() or "downloaded_item"
        full_path = os.path.join(output_path, f"{safe_title}{ext}")
        
        logging.info(f"Direct Download Target: {os.path.abspath(full_path)}")
        
        # Auto-rename on collision to prevent skipping different videos with same title
        base_name = safe_title
        counter = 1
        while os.path.exists(full_path):
            # Check if it's the SAME file? Hard to know without size/hash.
            # For safety, we assume collision and rename.
            # Exception: if size is 0, we overwrite (previous logic).
            if os.path.getsize(full_path) == 0:
                try:
                    os.remove(full_path)
                    break # Break loop to use this path
                except Exception: pass
            
            safe_title = f"{base_name}_{counter}"
            full_path = os.path.join(output_path, f"{safe_title}{ext}")
            counter += 1
            
        if not os.path.exists(output_path): os.makedirs(output_path)
        
        def report_hook(bn, bs, ts):
            if ts > 0: progress_callback(min(100, int((bn * bs * 100) / ts)))
            
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')]
        urllib.request.install_opener(opener)
        
        urllib.request.urlretrieve(url, full_path, report_hook)
        
        if settings.get('naming_style') == 'Video + Caption (.txt)':
            try:
                txt_f = os.path.splitext(full_path)[0] + ".txt"
                content = title
                if settings.get('remove_links'): content = re.sub(r'https?://\S+', '', content)
                if settings.get('remove_mentions'): content = re.sub(r'@\w+', '', content)
                with open(txt_f, 'w', encoding='utf-8') as f: f.write(content.strip())
            except Exception: pass
        progress_callback(100); return True, "Completed"
    except Exception: return False, "Failed"

def extract_pinterest_direct_url(url):
    if not PLAYWRIGHT_AVAILABLE: return None
    m3u8_url = None
    mp4_url = None
    seen_placeholder = False
    
    def handle_response(response):
        nonlocal m3u8_url, mp4_url, seen_placeholder
        if m3u8_url: return
        
        r_url = response.url
        if '10001_0100.mp4' in r_url:
            seen_placeholder = True
            return
        
        if response.request.resource_type == "media" or '.m3u8' in r_url or '.mp4' in r_url:
             if '.m3u8' in r_url: m3u3_url = r_url
             elif '.mp4' in r_url and not mp4_url: mp4_url = r_url

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            page = context.new_page(); page.on("response", handle_response)
            try: page.goto(url, timeout=30000, wait_until="domcontentloaded")
            except Exception: pass 
            
            start_time = time.time()
            while not m3u8_url and time.time() - start_time < 8: page.wait_for_timeout(500)
            
            final_url = m3u8_url if m3u8_url else mp4_url
            if final_url: 
                browser.close()
                return final_url
            
            if seen_placeholder:
                logging.warning("Only placeholder video found. ReelShort likely requires login/cookies to play this episode.")
            
            # Pinterest JSON fallback
            try:
                json_data = page.evaluate("() => document.getElementById('__PWS_DATA__') ? document.getElementById('__PWS_DATA__').innerText : null")
                if json_data:
                    data = json.loads(json_data)
                    def find_v(obj):
                        if isinstance(obj, dict):
                            if 'video_list' in obj:
                                vl = obj['video_list']
                                for k in ['V_720P', 'V_EXP7', 'V_HLSV3_MOBILE']:
                                    if k in vl: return vl[k]['url']
                                for k, v in vl.items():
                                    if 'url' in v: return v['url']
                            for k, v in obj.items():
                                r = find_v(v); 
                                if r: return r
                        elif isinstance(obj, list):
                            for i in obj:
                                r = find_v(i); 
                                if r: return r
                        return None
                    extracted = find_v(data)
                    if extracted: browser.close(); return extracted
            except Exception: pass
            
            # ReelShort / Next.js JSON fallback
            try:
                next_data = page.evaluate("() => document.getElementById('__NEXT_DATA__') ? document.getElementById('__NEXT_DATA__').innerText : null")
                if next_data:
                    data = json.loads(next_data)
                    # Navigate safe path: props.pageProps.data.video_url
                    try:
                        v_url = data.get('props', {}).get('pageProps', {}).get('data', {}).get('video_url')
                        if v_url and ('.m3u8' in v_url or '.mp4' in v_url):
                            logging.info(f"Found video in __NEXT_DATA__: {v_url}")
                            browser.close()
                            return v_url
                    except Exception: pass
            except Exception: pass
            
            # Video Tag fallback
            try:
                page.evaluate("() => { const v = document.querySelector('video'); if(v) v.play(); }"); time.sleep(2)
                # Check captured network vars again
                final = m3u8_url if m3u8_url else mp4_url
                if final: browser.close(); return final
                
                src = page.evaluate("() => document.querySelector('video') ? document.querySelector('video').src : null")
                if src and src.startswith('http') and '10001_0100.mp4' not in src: 
                    browser.close(); return src
            except Exception: pass
            browser.close()
    except Exception: pass
    return m3u8_url if m3u8_url else mp4_url

def extract_pinterest_image_url(url):
    if not PLAYWRIGHT_AVAILABLE: return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            page = context.new_page()
            try: page.goto(url, timeout=30000, wait_until="domcontentloaded")
            except Exception: pass 
            try:
                json_data = page.evaluate("() => document.getElementById('__PWS_DATA__') ? document.getElementById('__PWS_DATA__').innerText : null")
                if json_data:
                    data = json.loads(json_data)
                    def find_i(obj):
                        if isinstance(obj, dict):
                            if 'images' in obj and isinstance(obj['images'], dict):
                                imgs = obj['images']
                                if 'orig' in imgs: return imgs['orig']['url']
                                if 'large' in imgs: return imgs['large']['url']
                            for k, v in obj.items():
                                r = find_i(v); 
                                if r: return r
                        elif isinstance(obj, list):
                            for i in obj:
                                r = find_i(i); 
                                if r: return r
                        return None
                    extracted = find_i(data)
                    if extracted: browser.close(); return extracted
            except Exception: pass
            src = page.evaluate("() => { const mi = document.querySelector('meta[property=\"og:image\"]'); if(mi) return mi.content; const imgs = Array.from(document.querySelectorAll('img')); if(!imgs.length) return null; imgs.sort((a,b) => (b.width*b.height) - (a.width*a.height)); return imgs[0].src; }")
            browser.close(); return src
    except Exception: return None

class BaseHandler(ABC):
    @abstractmethod
    def can_handle(self, url): pass
    @abstractmethod
    def get_metadata(self, url): pass
    @abstractmethod
    def get_playlist_metadata(self, url, max_entries=100, settings={}, callback=None): pass
    @abstractmethod
    def download(self, item, progress_callback): pass
    def get_download_path(self, settings, is_video=True, item_url=None):
        base_path = settings.get('video_path' if is_video else 'photo_path') or settings.get('photo_path' if is_video else 'video_path') or '.'
        origin_url = settings.get('origin_url')
        if origin_url and item_url and origin_url.rstrip('/') != item_url.rstrip('/'):
            try:
                p = urlparse(origin_url.rstrip('/'))
                path = p.path.strip('/')
                fn = ""
                q = f"_{p.query.split('&')[0]}" if p.query else ""
                if 'youtube.com' in p.netloc or 'youtu.be' in p.netloc:
                    if 'playlist' in path:
                        from urllib.parse import parse_qs
                        qs = parse_qs(p.query)
                        if 'list' in qs: fn = f"Playlist_{qs['list'][0]}"
                    else: fn = path.replace('/', '_') + q
                else: fn = path.replace('/', '_') + q
                if fn:
                    safe = "".join([c for c in fn if c.isalpha() or c.isdigit() or c in (' ', '-', '_', '.')]).strip()
                    if safe: base_path = os.path.join(base_path, safe)
            except Exception: pass
        return base_path

class YouTubeHandler(BaseHandler):
    def can_handle(self, url): return 'youtube.com' in url or 'youtu.be' in url
    def get_metadata(self, url): return extract_metadata_with_playwright(url)
    def get_playlist_metadata(self, url, max_entries=100, settings={}, callback=None): return extract_metadata_with_ytdlp(url, max_entries, settings, callback=callback)
    def download(self, item, progress_callback): return download_with_ytdlp(item['url'], self.get_download_path(item.get('settings', {}), True, item['url']), progress_callback, item.get('settings', {}))

class TikTokHandler(BaseHandler):
    def can_handle(self, url): return 'tiktok.com' in url
    def get_metadata(self, url): return extract_metadata_with_playwright(url)
    def get_playlist_metadata(self, url, max_entries=100, settings={}, callback=None): return extract_metadata_with_ytdlp(url, max_entries, settings=settings, callback=callback)
    def download(self, item, progress_callback): return download_with_ytdlp(item['url'], self.get_download_path(item.get('settings', {}), True, item['url']), progress_callback, item.get('settings', {}))

class PinterestHandler(BaseHandler):
    def can_handle(self, url): return 'pinterest.com' in url
    def get_metadata(self, url): return extract_metadata_with_playwright(url)
    def get_playlist_metadata(self, url, max_entries=100, settings={}, callback=None): return extract_metadata_with_playwright(url, max_entries, settings=settings, callback=callback)
    def download(self, item, progress_callback):
        url = item['url']; title = item.get('title', 'Pinterest Download'); settings = item.get('settings', {})
        try:
            pid = ""; pts = url.strip('/').split('/')
            if 'pin' in pts:
                idx = pts.index('pin')
                if idx + 1 < len(pts): pid = pts[idx+1]
            if not pid:
                for pt in reversed(pts):
                    if pt.isdigit(): pid = pt; break
            if pid and pid not in title: title = f"{title}_{pid}"
            safe_t = "".join([c for c in title if c.isalpha() or c.isdigit() or c in (' ', '_', '-')]).strip() or (f"pinterest_{pid}" if pid else "pinterest_download")
            settings['forced_filename'] = safe_t
        except Exception: pass
        is_i = url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
        op = self.get_download_path(settings, not is_i, url)
        if is_i: return download_direct(url, op, title, progress_callback, settings)
        settings['suppress_expected_errors'] = True 
        s, _ = download_with_ytdlp(url, op, progress_callback, settings)
        if s: return True
        du = extract_pinterest_direct_url(url)
        if du: return download_with_ytdlp(du, op, progress_callback, settings)
        iu = extract_pinterest_image_url(url)
        if iu: return download_direct(iu, self.get_download_path(settings, False, url), title, progress_callback, settings)
        return False

class FacebookHandler(BaseHandler):
    def can_handle(self, url): return bool(re.search(r'facebook\.com/(?:video\.php\?v=|watch/\?v=|reel/|story\.php\?story_fbid=|[^/]+/videos/|[^/]+/reels/)|fb\.watch/', url)) or 'sk=videos' in url or 'sk=reels_tab' in url
    def get_metadata(self, url): return extract_metadata_with_playwright(url)
    def get_playlist_metadata(self, url, max_entries=100, settings={}, callback=None): return extract_metadata_with_playwright(url, max_entries, settings=settings, callback=callback)
    def download(self, item, progress_callback): return download_with_ytdlp(item['url'], self.get_download_path(item.get('settings', {}), True, item['url']), progress_callback, item.get('settings', {}))

class InstagramHandler(BaseHandler):
    def can_handle(self, url): return 'instagram.com' in url
    def get_metadata(self, url): return extract_metadata_with_playwright(url)
    def get_playlist_metadata(self, url, max_entries=100, settings={}, callback=None): return extract_metadata_with_playwright(url, max_entries, settings=settings, callback=callback)
    def download(self, item, progress_callback):
        url = item['url']; settings = item.get('settings', {})
        is_i = url.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
        op = self.get_download_path(settings, not is_i, url)
        if is_i: return download_direct(url, op, item.get('title', 'Instagram Download'), progress_callback, settings)
        return download_with_ytdlp(url, op, progress_callback, settings)

class KuaishouHandler(BaseHandler):
    def can_handle(self, url): return 'kuaishou.com' in url or 'kwai.com' in url
    def get_metadata(self, url): return extract_metadata_with_playwright(url)
    def get_playlist_metadata(self, url, max_entries=100, settings={}, callback=None): return extract_metadata_with_playwright(url, max_entries, settings=settings, callback=callback)
    def download(self, item, progress_callback): return download_with_ytdlp(item['url'], self.get_download_path(item.get('settings', {}), True, item['url']), progress_callback, item.get('settings', {}))

class ReelShortHandler(BaseHandler):
    def can_handle(self, url): return 'reelshort.com' in url
    def get_metadata(self, url): return extract_metadata_with_playwright(url)
    def get_playlist_metadata(self, url, max_entries=100, settings={}, callback=None): return extract_metadata_with_playwright(url, max_entries, settings=settings, callback=callback)
    def download(self, item, progress_callback):
        url = item['url']; settings = item.get('settings', {}); op = self.get_download_path(settings, True, url)
        s, _ = download_with_ytdlp(url, op, progress_callback, settings)
        if s: return True
        du = extract_pinterest_direct_url(url)
        if du:
            logging.info(f"Found direct video URL: {du}")
            # If it's HLS (m3u8), we MUST use yt-dlp to process/convert it
            if '.m3u8' in du:
                # Force mp4 extension for output
                settings['extension'] = 'mp4'
                return download_with_ytdlp(du, op, progress_callback, settings)
            else:
                # Direct file (mp4), use urllib
                return download_direct(du, op, item.get('title', 'ReelShort_Video'), progress_callback, settings)
        return False

class DramaboxHandler(BaseHandler):
    def can_handle(self, url): return 'dramaboxdb.com' in url
    
    def get_metadata(self, url): return extract_metadata_with_playwright(url)
    
    def get_playlist_metadata(self, url, max_entries=100, settings={}, callback=None):
        if not PLAYWRIGHT_AVAILABLE:
            return [{'url': url, 'title': 'Error: Playwright Missing', 'type': 'error'}]

        results = []
        try:
            with sync_playwright() as p:
                try:
                    browser = p.chromium.launch(headless=True)
                except Exception as e:
                    logging.error(f"Error launching browser: {e}")
                    return [{'url': url, 'title': 'Error: Browser Launch Failed', 'type': 'error'}]

                context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
                page = context.new_page()
                
                logging.info(f"Dramabox scraping: {url}")
                try:
                    page.goto(url, timeout=60000, wait_until="domcontentloaded")
                    time.sleep(3)
                    
                    all_episodes = set()
                    unique_urls = set()
                    page_num = 1
                    
                    while len(results) < max_entries:
                        logging.info(f"Scraping Dramabox page {page_num}")
                        
                        # Extract Links
                        links_data = page.evaluate("""
                            () => {
                                return Array.from(document.querySelectorAll('a[href*="/ep/"]')).map(a => {
                                    return {href: a.href, text: a.innerText || 'Episode'};
                                });
                            }
                        """)
                        
                        new_items = 0
                        for l in links_data:
                            link = l['href']
                            text = l['text'].strip()
                            if link not in all_episodes:
                                all_episodes.add(link)
                                clean_link = link.split('#')[0].split('?')[0]
                                if clean_link not in unique_urls:
                                    unique_urls.add(clean_link)
                                    
                                    # Extract episode number from URL (format: ..._Episode-1)
                                    ep_match = re.search(r'Episode-(\d+)', clean_link)
                                    display_title = text
                                    if ep_match:
                                        ep_num = ep_match.group(1)
                                        # Avoid redundancy if text is just the number or "Episode X"
                                        if text.isdigit() or text.lower() == f"episode {ep_num}":
                                            display_title = f"epsode-{ep_num}"
                                        else:
                                            display_title = f"epsode-{ep_num} {text}"
                                    elif text.isdigit(): # Fallback if text is just the number
                                        display_title = f"epsode-{text}"
                                        
                                    item = {'url': clean_link, 'title': display_title, 'type': 'scraped_link'}
                                    results.append(item)
                                    if callback: callback(item)
                                    new_items += 1
                        
                        if new_items == 0 and page_num > 1:
                            logging.info("No new items found. Stopping.")
                            break
                        
                        # Pagination Logic
                        buttons = page.locator(".RightList_tabTitle__zvZRp").all()
                        if page_num < len(buttons):
                            logging.info(f"Clicking tab index {page_num}...")
                            buttons[page_num].click()
                            time.sleep(3)
                            page_num += 1
                        else:
                            logging.info("No more tabs to click.")
                            break
                            
                        if page_num > 20: break # Safety limit

                except Exception as e:
                    logging.error(f"Dramabox scrape error: {e}")
                finally:
                    browser.close()
        except Exception as e:
             logging.error(f"Playwright error: {e}")
             results.append({'url': url, 'title': 'Scrape Error', 'type': 'error'})
        return results

    def download(self, item, progress_callback):
        # Default to yt-dlp for now, as it handles generic HLS/mp4 often found on these sites
        # If it fails, we might need a custom extraction similar to ReelShort
        return download_with_ytdlp(item['url'], self.get_download_path(item.get('settings', {}), True, item['url']), progress_callback, item.get('settings', {}))

class PlatformHandlerFactory:
    def __init__(self):
        self.handlers = [YouTubeHandler(), TikTokHandler(), PinterestHandler(), FacebookHandler(), InstagramHandler(), KuaishouHandler(), ReelShortHandler(), DramaboxHandler()]
    def get_handler(self, url):
        for h in self.handlers:
            if h.can_handle(url): return h
        return None