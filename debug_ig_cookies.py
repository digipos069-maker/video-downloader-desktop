
import os
import sys
from playwright.sync_api import sync_playwright
import time

# --- Copied from app/platform_handler.py ---
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
        print(f"Error parsing cookie file: {e}")
    return cookies
# -------------------------------------------

def debug_instagram_cookies():
    cookie_file = r"C:/Users/USER/Downloads/www.instagram.com_cookies.txt"
    target_url = "https://www.instagram.com/instagram/"

    print(f"Debug: Testing Instagram Cookies")
    print(f"Cookie File: {cookie_file}")
    
    if not os.path.exists(cookie_file):
        print("ERROR: Cookie file does not exist!")
        return

    parsed_cookies = parse_cookie_file(cookie_file)
    print(f"Parsed {len(parsed_cookies)} cookies.")
    
    # Debug: Print a few cookie names to verify parsing
    if parsed_cookies:
        print(f"Sample cookies: {[c['name'] for c in parsed_cookies[:5]]}")
    else:
        print("WARNING: No cookies parsed.")

    with sync_playwright() as p:
        print("Launching browser...")
        # Launch headless=False to visually see if needed (but running via shell so maybe stick to logs)
        # We'll use headless=True but capture title and content
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        
        if parsed_cookies:
            try:
                context.add_cookies(parsed_cookies)
                print("Cookies added to context.")
            except Exception as e:
                print(f"Failed to add cookies: {e}")
        
        page = context.new_page()
        
        print(f"Navigating to {target_url}...")
        try:
            page.goto(target_url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(5) # Wait for redirects or dynamic loads
            
            title = page.title()
            print(f"Page Title: {title}")
            
            # Check for login indicators
            content = page.content()
            if "Login" in title or "Log In" in title:
                print("FAIL: Title indicates Login page.")
            elif 'name="username"' in content and 'name="password"' in content:
                 print("FAIL: Login form detected in content.")
            else:
                print("SUCCESS: Doesn't look like a login page.")
                
            # Take a screenshot for manual verification if possible (saved to temp) 
            screenshot_path = "debug_ig_screenshot.png"
            page.screenshot(path=screenshot_path)
            print(f"Screenshot saved to {screenshot_path}")

        except Exception as e:
            print(f"Navigation error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    debug_instagram_cookies()
