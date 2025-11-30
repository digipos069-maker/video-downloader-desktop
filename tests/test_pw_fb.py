from app.platform_handler import extract_metadata_with_playwright
import logging

logging.basicConfig(level=logging.DEBUG)

url = "https://www.facebook.com/watch/?v=10153231379986729"
print(f"Testing Playwright with URL: {url}")

results = extract_metadata_with_playwright(url)
print("Results:", results)
