import os
import shutil
import sys
import subprocess

def get_playwright_browsers_path():
    # Try getting path from playwright command
    try:
        # This is a bit hacky, but 'playwright install --dry-run' usually prints the path
        # Alternatively, use the default location
        if sys.platform == 'win32':
            return os.path.join(os.environ['LOCALAPPDATA'], 'ms-playwright')
        elif sys.platform == 'darwin':
            return os.path.join(os.environ['HOME'], 'Library', 'Caches', 'ms-playwright')
        else:
            return os.path.join(os.environ['HOME'], '.cache', 'ms-playwright')
    except Exception as e:
        print(f"Error determining path: {e}")
        return None

def copy_browsers():
    source_path = get_playwright_browsers_path()
    dest_path = os.path.join(os.getcwd(), 'playwright-browsers')

    if not os.path.exists(source_path):
        print(f"Could not find Playwright browsers at: {source_path}")
        print("Please run 'playwright install' first.")
        return

    print(f"Found browsers at: {source_path}")
    print(f"Copying to: {dest_path} ...")
    
    if os.path.exists(dest_path):
        print("Destination folder already exists. Skipping copy to avoid overwriting.")
        print("Delete 'playwright-browsers' folder if you want to refresh it.")
        return

    try:
        shutil.copytree(source_path, dest_path)
        print("Success! Browsers copied.")
        print("Now, when you build/distribute your app, include this 'playwright-browsers' folder")
        print("alongside your executable (or inside the _internal folder).")
    except Exception as e:
        print(f"Error copying files: {e}")

if __name__ == "__main__":
    copy_browsers()
