from playwright.sync_api import sync_playwright
import time
import logging
import json
import os
from app.platform_handler import parse_cookie_file

logging.basicConfig(level=logging.INFO)

def inspect_reelshort_media(url):
    print(f"Inspecting: {url}")
    
    # Load Cookies
    cookies = []
    try:
        with open("app/config/credentials.json", "r") as f:
            creds = json.load(f)
            cookie_path = creds.get("reelshort", {}).get("cookie_file", "")
            if cookie_path and os.path.exists(cookie_path):
                print(f"Loading cookies from: {cookie_path}")
                cookies = parse_cookie_file(cookie_path)
            else:
                print("No ReelShort cookie file found in config.")
    except Exception as e:
        print(f"Failed to load credentials: {e}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) # Change to False if you want to see it
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        if cookies:
            context.add_cookies(cookies)
            
        page = context.new_page()
        
        media_urls = []
        
        def handle_response(response):
            if response.request.resource_type == "media" or '.m3u8' in response.url or '.mp4' in response.url:
                print(f"Caught Media: {response.url}")
                media_urls.append(response.url)

        page.on("response", handle_response)
        
        try:
            page.goto(url, timeout=60000, wait_until="networkidle")
            time.sleep(10) # Wait for player to load fully
        except Exception as e:
            print(f"Page load error: {e}")
            
        print("\n--- Summary of Media URLs ---")
        for u in media_urls:
            print(u)
            
        browser.close()

if __name__ == "__main__":
    url = "https://www.reelshort.com/episodes/episode-72-step-aside-i-m-the-king-of-capital-690306d7afd90472c800cf3a-0dmps4dewm"
    inspect_reelshort_media(url)
