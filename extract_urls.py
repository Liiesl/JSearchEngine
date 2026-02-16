import json
import os
import time

import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
SITEMAP_TEMPLATE = "https://www.javdatabase.com/movies-sitemap{}.xml"
TOTAL_SITEMAPS = 459  # As per your instruction
OUTPUT_FILE = "movie_links.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.7093.0 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
}


def main():
    all_urls = []

    print(f"🚀 Starting Sitemap Extraction (1 to {TOTAL_SITEMAPS})...")

    for i in range(1, TOTAL_SITEMAPS + 1):
        url = SITEMAP_TEMPLATE.format(i)
        print(f"   reading sitemap {i}/{TOTAL_SITEMAPS}...", end="\r")

        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                # Use 'lxml-xml' or 'xml' if installed, otherwise 'html.parser' works for simple XML too
                soup = BeautifulSoup(resp.content, "xml")

                # Extract content inside <loc> tags
                locs = soup.find_all("loc")
                count = 0
                for loc in locs:
                    link = loc.text.strip()
                    # Basic filter to ensure it's a movie link
                    if "/movies/" in link:
                        all_urls.append(link)
                        count += 1

                # Optional: Sleep slightly to be polite
                time.sleep(0.2)
            else:
                print(f"\n❌ Error on map {i}: Status {resp.status_code}")

        except Exception as e:
            print(f"\n❌ Exception on map {i}: {e}")

    # Remove duplicates just in case
    unique_urls = list(set(all_urls))

    print(f"\n\n✅ Extraction Complete!")
    print(f"   Found {len(all_urls)} total URLs.")
    print(f"   Unique URLs: {len(unique_urls)}")

    # Save to JSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(unique_urls, f, indent=2)

    print(f"💾 Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
