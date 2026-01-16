
from playwright.sync_api import sync_playwright
import json
import logging

logging.basicConfig(level=logging.INFO)

def inspect_next_data(url):
    print(f"Inspecting __NEXT_DATA__: {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        
        # Extract content of script id="__NEXT_DATA__"
        json_content = page.evaluate("""
            () => {
                const script = document.getElementById('__NEXT_DATA__');
                return script ? script.innerText : null;
            }
        """)
        
        if json_content:
            data = json.loads(json_content)
            print("Successfully parsed __NEXT_DATA__")
            
            # Recursive search for 'm3u8' or 'mp4'
            def find_media(obj, path=""):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        find_media(v, f"{path}.{k}")
                        if isinstance(v, str) and ('.m3u8' in v or '.mp4' in v):
                            print(f"FOUND MEDIA at {path}.{k}: {v}")
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        find_media(item, f"{path}[{i}]")
                        if isinstance(item, str) and ('.m3u8' in item or '.mp4' in item):
                            print(f"FOUND MEDIA at {path}[{i}]: {item}")

            find_media(data)
        else:
            print("No __NEXT_DATA__ found.")
            
        browser.close()

if __name__ == "__main__":
    url = "https://www.reelshort.com/episodes/episode-72-step-aside-i-m-the-king-of-capital-690306d7afd90472c800cf3a-0dmps4dewm"
    inspect_next_data(url)
