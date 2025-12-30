import os
import time
from playwright.sync_api import sync_playwright

def debug_pinterest_logic(url):
    print(f"\n--- DEBUG: PINTEREST SCRAPE LOGIC ---")
    print(f"Target URL: {url}")

    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print("Navigating to Pinterest...")
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(5)
            
            print("Extracting and sorting items...")
            # Use a simpler, more robust extraction script for debug purposes
            results = page.evaluate(
                """
                () => {
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    const data = links
                        .filter(a => a.href.includes('pinterest.com/pin/'))
                        .map(a => {
                            const rect = a.getBoundingClientRect();
                            const container = a.closest('[data-test-id="pin"], .pin, .post, article');
                            let isVideo = false;
                            let title = a.innerText || a.getAttribute('aria-label') || "No Title";
                            
                            if (container) {
                                if (container.querySelector('video, [aria-label*="video"], .video-icon')) isVideo = true;
                                if (/\\d+\\:\\d+/.test(container.innerText)) isVideo = true;
                            }

                            return {
                                url: a.href.split('?')[0],
                                title: title.split('\\n')[0].substring(0, 30),
                                top: Math.round(rect.top + window.scrollY),
                                left: Math.round(rect.left + window.scrollX),
                                isVideo: isVideo
                            };
                        });
                    
                    // Deduplicate
                    const unique = {};
                    data.forEach(d => { if(!unique[d.url]) unique[d.url] = d; });
                    
                    // Sort
                    return Object.values(unique).sort((a, b) => {
                        const rowDiff = a.top - b.top;
                        if (Math.abs(rowDiff) > 150) return rowDiff;
                        return a.left - b.left;
                    });
                }
            """
            )
            
            print(f"\nFound {len(results)} unique pins. First 15 in order:")
            print(f"{ '#':<3} | { 'Type':<10} | { 'Top':<6} | { 'Left':<6} | { 'Title'}")
            print("-" * 65)
            
            for i, item in enumerate(results[:15]):
                item_type = "VIDEO 🎥" if item['isVideo'] else "PHOTO 🖼️"
                print(f"{i+1:<3} | {item_type:<10} | {item['top']:<6} | {item['left']:<6} | {item['title']}")

            videos = [r for r in results if r['isVideo']]
            print(f"\nTotal Videos: {len(videos)}")
            print(f"Total Photos: {len(results) - len(videos)}")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    test_url = "https://www.pinterest.com/search/pins/?q=cooking%20videos"
    debug_pinterest_logic(test_url)
