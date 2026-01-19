
from playwright.sync_api import sync_playwright
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_dramabox_scrape(url):
    print(f"Testing DramaBox Scraping: {url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Headless=False to see what happens
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = context.new_page()
        
        try:
            logging.info(f"Navigating to {url}...")
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(3) # Wait for initial load
            
            # 1. Find and click 'View More' button
            try:
                view_more_selector = ".pcSeries_viewMore__Saxsu"
                if page.is_visible(view_more_selector):
                    logging.info("Found 'View More' button. Clicking...")
                    page.click(view_more_selector)
                    time.sleep(2) # Wait for expansion
                else:
                    logging.warning("'View More' button not visible or not found.")
            except Exception as e:
                logging.error(f"Error clicking 'View More': {e}")
            
            # Scrape loop with pagination
            all_episodes = set()
            page_num = 1
            
            while True:
                logging.info(f"--- Scraping Page {page_num} ---")
                
                # Extract Links
                # User said format: https://www.dramaboxdb.com/ep/...
                # We look for links containing '/ep/'
                links = page.evaluate("""
                    () => {
                        return Array.from(document.querySelectorAll('a[href*="/ep/"]')).map(a => a.href);
                    }
                """)
                
                new_links = 0
                for link in links:
                    if link not in all_episodes:
                        all_episodes.add(link)
                        print(f"Found Episode: {link}")
                        new_links += 1
                
                logging.info(f"Found {new_links} new episodes on this page.")
                
                if new_links == 0:
                    logging.warning("No new episodes found on this page.")
                
                # Pagination: Find 'Next' button
                # User didn't give class for 'Next'. We need to guess or find generic 'Next' or icon.
                # Common pagination classes/text: "Next", ">", "next-page", etc.
                # Let's inspect potential pagination elements.
                
                # Try to find a "Next" button.
                # Heuristics:
                # 1. Text "Next"
                # 2. Aria label "Next"
                # 3. Class containing "next" (and clickable)
                
                next_button = None
                
                # Strategy 1: Look for exact text or likely text
                candidates = page.get_by_text("Next", exact=True)
                if candidates.count() > 0:
                    next_button = candidates.first
                
                # Strategy 2: Common pagination classes (if user didn't specify, I have to guess or check DOM)
                if not next_button:
                     # Check for generic pagination next
                     # This is a guess. The user said "find next pagination click next".
                     # I'll dump some buttons to see what looks like pagination if this fails.
                     pass
                
                # For now, since I don't know the exact "Next" selector, I will try to identify it.
                # If I can't find it easily, I might stop after page 1 for this debug run.
                # BUT, the user gave a specific flow.
                
                # Let's try to capture generic pagination buttons
                try:
                    # Look for a button or link that acts as "Next"
                    # Often pagination is in a ul/li/a structure or just buttons.
                    # Let's assume standard 'ant-pagination-next' or similar if using a library, 
                    # or just look for the last 'a' or 'button' in a pagination container.
                    
                    # Try to find elements that look like pagination
                    pagination_el = page.query_selector('.pagination, [class*="pagination"], .pages')
                    if pagination_el:
                        # try to find 'next' inside
                        pass
                    
                    # Attempt to find 'Next' by text/arrow
                    next_btn = page.locator("li.next, button.next, a.next, [aria-label='Next Page'], .rc-pagination-next").first
                    if next_btn.is_visible():
                         logging.info("Found likely Next button (heuristic).")
                         next_button = next_btn
                    else:
                        # Try searching for text ">"
                        next_arrow = page.get_by_text(">", exact=True).first
                        if next_arrow.is_visible():
                             next_button = next_arrow
                except Exception: pass

                if next_button and next_button.is_visible() and next_button.is_enabled():
                    logging.info("Clicking Next...")
                    next_button.click()
                    time.sleep(3) # Wait for page load
                    page_num += 1
                else:
                    logging.info("No 'Next' button found or enabled. Reached end.")
                    break
                    
                if page_num > 5: # Safety break
                    logging.info("Debug limit reached (5 pages).")
                    break

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            
        finally:
            browser.close()

if __name__ == "__main__":
    test_url = "https://www.dramaboxdb.com/ep/42000000606_his-love-was-a-lie/700038723_Episode-1"
    
    # Redefine function inside to update logic without rewriting whole file
    def test_dramabox_scrape(url):
        print(f"Testing DramaBox Scraping: {url}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            
            try:
                logging.info(f"Navigating to {url}...")
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                time.sleep(3)
                
                # No 'View More' step mentioned for this new flow, starting directly
                
                all_episodes = set()
                page_num = 1
                
                while True:
                    logging.info(f"--- Scraping Page {page_num} ---")
                    
                    # Extract Links
                    links = page.evaluate("""
                        () => {
                            return Array.from(document.querySelectorAll('a[href*="/ep/"]')).map(a => a.href);
                        }
                    """)
                    
                    new_links = 0
                    for link in links:
                        if link not in all_episodes:
                            all_episodes.add(link)
                            print(f"Found Episode: {link}")
                            new_links += 1
                    
                    logging.info(f"Found {new_links} new episodes on this page.")
                    
                    if new_links == 0:
                        logging.warning("No new episodes found on this page. Might be end.")
                        # break # Optional: break if no new links, but maybe next page has some?
                    
                    # Pagination: Click 'RightList_tabTitle__zvZRp'
                    # User said: "click find button next by click on button class RightList_tabTitle__zvZRp"
                    # This class name sounds like a Tab Title, not necessarily a "Next" button.
                    # It implies switching tabs? Or maybe it loads the next set of episodes?
                    # Let's try to click it.
                    
                    next_button_selector = ".RightList_tabTitle__zvZRp"
                    
                    # Check if there are multiple? User said "click on button class ...".
                    # If it's a pagination next, usually there's one active one or one specific "Next".
                    # If it is a list of tabs (e.g. "1-50", "51-100"), we might need to click the *next* one.
                    
                    # Let's inspect what elements have this class.
                    # If it's a tab list, we need to click the one that corresponds to the next batch.
                    
                    # Assuming for now it acts as a "Next Page" or "Load More" button based on description.
                    # Or maybe we need to iterate through them?
                    
                    # Heuristic: Find all such elements, see which one is "active", click the next one?
                    # Or if it's a single "Next" button.
                    
                    # Let's try to find them.
                    buttons = page.locator(next_button_selector).all()
                    if not buttons:
                        logging.warning(f"No element found with class {next_button_selector}")
                        break
                        
                    logging.info(f"Found {len(buttons)} elements with class {next_button_selector}")
                    
                    # If multiple, logic needed.
                    # Example: Tabs for "1-100", "101-200". 
                    # If so, we need to find the currently active one and click the next.
                    # Or just click them one by one?
                    
                    # Since I don't know the exact UI state (active class?), I'll assume we need to click the *next* unclicked one?
                    # Or maybe the user meant the button *inside* a container?
                    
                    # Let's try: Find the one that contains "Next" or ">"?
                    # Or if it's tabs, click the next index.
                    
                    # Hack: For this debug, I will try to click the *next* tab index based on page_num.
                    # Page 1 -> Default. Page 2 -> Click 2nd tab?
                    # Arrays are 0-indexed.
                    
                    if page_num < len(buttons):
                        # Click the next tab (index = page_num)
                        # Page 1 (current) is likely index 0. We want to go to Page 2 (index 1).
                        logging.info(f"Clicking tab index {page_num}...")
                        buttons[page_num].click()
                        time.sleep(3)
                        page_num += 1
                    else:
                        logging.info("No more tabs/buttons to click.")
                        break
                        
                    if page_num > 10: break

            except Exception as e:
                logging.error(f"An error occurred: {e}")
            finally:
                browser.close()

    test_dramabox_scrape(test_url)
