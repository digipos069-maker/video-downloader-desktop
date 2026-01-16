from playwright.sync_api import sync_playwright
import time
import logging
import json

logging.basicConfig(level=logging.INFO)

def deep_scan_reelshort(url):
    print(f"Deep Scanning: {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Capture potential video sources
        candidates = []
        
        def handle_response(response):
            u = response.url
            ct = response.headers.get("content-type", "")
            
            # 1. Direct Media
            if "video" in ct or ".m3u8" in u or ".mp4" in u:
                candidates.append(f"[MEDIA] {u}")
                
            # 2. Manifests / JSON (Player Config)
            if "json" in ct and ("player" in u or "video" in u or "vod" in u):
                try:
                    data = response.json()
                    candidates.append(f"[JSON] {u}")
                    # Basic scan of JSON for .m3u8
                    str_data = json.dumps(data)
                    if ".m3u8" in str_data or ".mp4" in str_data:
                        candidates.append(f"  -> FOUND MEDIA IN JSON!")
                except: pass

        page.on("response", handle_response)
        
        try:
            page.goto(url, timeout=60000, wait_until="networkidle")
            time.sleep(5)
            
            # 3. Check Page Source for hidden data
            content = page.content()
            if "__NEXT_DATA__" in content:
                print("[HTML] Found __NEXT_DATA__")
                # Extract it?
                # ...
                
        except Exception as e:
            print(f"Page load error: {e}")
            
        print("\n--- Deep Scan Results ---")
        for c in candidates:
            print(c)
            
        browser.close()

if __name__ == "__main__":
    # Test with the problematic episode
    url = "https://www.reelshort.com/episodes/episode-72-step-aside-i-m-the-king-of-capital-690306d7afd90472c800cf3a-0dmps4dewm"
    deep_scan_reelshort(url)
