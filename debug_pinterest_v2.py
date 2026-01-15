import time
import logging
import os
import re
import json
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

# Setup minimal logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_cookie_file(cookie_file):
    """
    Parses a Netscape format cookie file into a list of dicts for Playwright.
    """
    cookies = []
    try:
        if not os.path.exists(cookie_file):
            logging.error(f"Cookie file not found: {cookie_file}")
            return []
            
        with open(cookie_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                
                parts = line.strip().split('\t')
                if len(parts) >= 7:
                    domain = parts[0]
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
                        'httpOnly': False,
                        'secure': secure,
                        'sameSite': 'Lax'
                    }
                    cookies.append(cookie)
    except Exception as e:
        logging.error(f"Error parsing cookie file: {e}")
    return cookies

def is_valid_media_link(href, domain):
    media_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.mkv', '.avi', '.mov', '.webm')
    if href.lower().endswith(media_extensions): return True
    if 'pinterest.com' in domain:
        return bool(re.search(r'/pin/\d+(?:/|\?|$)', href)) and not re.search(r'/pin/\d+/.+', href)
    return False

def extract_metadata_with_playwright(url, max_entries=10, settings={}):
    results = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # LOAD COOKIES
            cookie_file = settings.get('cookie_file')
            if cookie_file:
                cookies = parse_cookie_file(cookie_file)
                if cookies:
                    context.add_cookies(cookies)
                    logging.info(f"Loaded {len(cookies)} cookies into context.")
            
            page = context.new_page()
            
            logging.info(f"Playwright visiting: {url}")
            try:
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                
                # WAIT 5 SECONDS BEFORE INITIAL SCREENSHOT
                logging.info("Waiting 5 seconds for page to settle...")
                time.sleep(5.0)
                
                # INITIAL SCREENSHOT (WITH COOKIES)
                initial_ss = "debug_pinterest_cookie_initial_5s.png"
                page.screenshot(path=initial_ss)
                logging.info(f"Initial (Cookie) 5s screenshot saved to {initial_ss}")
                
                # Retrieve Filtering Settings
                req_video = settings.get('video_enabled', True) 
                req_photo = settings.get('photo_enabled', True)
                
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.replace('www.', '')
                
                unique_urls = set()
                all_seen_links = set()
                results = []

                extract_func = """
                    () => {
                        const items = Array.from(document.querySelectorAll('a[href]')).map(a => {
                            let t = a.innerText;
                            const rect = a.getBoundingClientRect();
                            const container = a.closest('[data-test-id="pin"], .pin, .post, article, [role="link"]');
                            return {
                                url: a.href, text: t, top: rect.top + window.scrollY, left: rect.left + window.scrollX, is_video_hint: !!(container && container.querySelector('video'))
                            };
                        });
                        const unique = new Map();
                        items.forEach(item => {
                            if (!item.url || !item.url.startsWith('http')) return;
                            if (!unique.has(item.url)) unique.set(item.url, item);
                        });
                        return Array.from(unique.values()).sort((a, b) => (a.top - b.top) || (a.left - b.left));
                    }
                """
                
                if '/pin/' in url:
                    logging.info("Single Pin detected. Triggering scroll.")
                    page.keyboard.press("End")
                    time.sleep(2.0)
                
                iteration = 0
                while len(results) < max_entries and iteration < 5:
                    iteration += 1
                    page.keyboard.press("PageDown")
                    time.sleep(1.0)
                    
                    extracted_links = page.evaluate(extract_func)
                    
                    new_found = 0
                    for link in extracted_links:
                        href = link['url']
                        clean_href = href.split('#')[0].split('?')[0].rstrip('/')
                        if clean_href in unique_urls: continue
                        if not is_valid_media_link(href, domain): continue
                        
                        unique_urls.add(clean_href)
                        results.append({'url': clean_href})
                        new_found += 1
                    
                    if new_found == 0: break
                
                screenshot_path = "debug_pinterest_cookie_result.png"
                page.screenshot(path=screenshot_path)
                logging.info(f"Result (Cookie) screenshot saved to {screenshot_path}")

            except Exception as e:
                logging.error(f"Error: {e}")
            finally:
                browser.close()
    except Exception as e:
        logging.error(f"System Error: {e}")
    return results

if __name__ == "__main__":
    url = "https://www.pinterest.com/pin/2111131073297692"
    # PATH FROM credentials.json
    cookie_path = "C:/Users/USER/Downloads/www.pinterest.com_cookies.txt"
    
    settings = {
        'video_enabled': False, 
        'photo_enabled': True,
        'cookie_file': cookie_path
    }
    
    print(f"Running debug WITH COOKIES for: {url}")
    items = extract_metadata_with_playwright(url, max_entries=5, settings=settings)
    
    print("\n--- RESULTS ---")
    for item in items:
        print(f" - {item['url']}")