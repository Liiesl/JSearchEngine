import json
import os
import time

import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
EXISTING_FILE = "movie_links.json"
SITEMAP_TEMPLATE = "https://www.javdatabase.com/movies-sitemap{}.xml"

# List the numbers that failed here:
MAPS_TO_REDO = [291, 330, 354]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def main():
    # 1. Load existing URLs
    if os.path.exists(EXISTING_FILE):
        print(f"📂 Loading existing {EXISTING_FILE}...")
        with open(EXISTING_FILE, "r", encoding="utf-8") as f:
            existing_urls = json.load(f)
        print(f"   Currently has {len(existing_urls)} URLs.")
    else:
        print(f"⚠️ {EXISTING_FILE} not found. Starting fresh.")
        existing_urls = []

    newly_found_urls = []

    # 2. Iterate only through the failed maps
    print(f"🚀 Starting Retry for maps: {MAPS_TO_REDO}")

    for map_num in MAPS_TO_REDO:
        url = SITEMAP_TEMPLATE.format(map_num)
        success = False
        attempts = 0
        max_retries = 3

        # Retry loop for unstable network
        while not success and attempts < max_retries:
            try:
                print(f"   Trying map {map_num} (Attempt {attempts + 1})...", end="\r")

                # Increased timeout to 30 seconds for unstable network
                resp = requests.get(url, headers=HEADERS, timeout=30)

                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.content, "xml")
                    locs = soup.find_all("loc")

                    count = 0
                    for loc in locs:
                        link = loc.text.strip()
                        if "/movies/" in link:
                            newly_found_urls.append(link)
                            count += 1

                    print(
                        f"   ✅ Map {map_num} Success! Found {count} links.          "
                    )
                    success = True
                else:
                    print(f"   ⚠️ Map {map_num} Error: Status {resp.status_code}")
                    attempts += 1
                    time.sleep(5)  # Wait 5 seconds before retrying

            except Exception as e:
                print(f"   ⚠️ Map {map_num} Exception: {e}")
                attempts += 1
                time.sleep(5)  # Wait 5 seconds before retrying

        if not success:
            print(f"   ❌ Map {map_num} FAILED after {max_retries} attempts.")

    # 3. Merge and Save
    if newly_found_urls:
        print(f"\n🔄 Merging data...")
        total_combined = existing_urls + newly_found_urls

        # Remove duplicates
        unique_combined = list(set(total_combined))

        added_count = len(unique_combined) - len(existing_urls)

        print(f"   Old Total: {len(existing_urls)}")
        print(f"   New Found: {len(newly_found_urls)}")
        print(f"   Actually Added (ignoring duplicates): {added_count}")
        print(f"   New Total: {len(unique_combined)}")

        with open(EXISTING_FILE, "w", encoding="utf-8") as f:
            json.dump(unique_combined, f, indent=2)

        print(f"💾 Updated {EXISTING_FILE} successfully.")
    else:
        print("\n⚠️ No new URLs were extracted.")


if __name__ == "__main__":
    main()
