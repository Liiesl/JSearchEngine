import json
import os
import random
import re
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

import requests
from bs4 import BeautifulSoup, NavigableString

# --- CONFIGURATION ---
INPUT_FILE = "upgrade_targets.txt"      # The list of slugs from compile_targets.py
OUTPUT_FILE = "scraped_profiles.jsonl"  # Where the new bio data goes
LOG_FILE = "profile_scrape_history.txt"
BASE_URL = "https://www.javdatabase.com/idols/"

MAX_WORKERS = 2
MAX_QUEUE_SIZE = MAX_WORKERS * 4

# Headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Referer": "https://www.javdatabase.com/",
}

# --- THREADING LOCKS & GLOBALS ---
file_lock = threading.Lock()
console_lock = threading.Lock()
processed_count = 0
total_tasks = 0

session = requests.Session()
session.headers.update(HEADERS)


def load_history():
    if not os.path.exists(LOG_FILE):
        return set()
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)


def append_history(slug):
    with file_lock:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(slug + "\n")


def save_profile_data(data):
    with file_lock:
        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())


def extract_value(soup, label_text):
    """
    Finds a <b>Label:</b> tag and extracts the single value following it.
    Handles text nodes (e.g., "86-57-87" or "?") and <a> tags (e.g., "156 cm").
    Stops at " - " separators or <br> tags.
    """
    label_tag = soup.find("b", string=lambda t: t and label_text in t)
    if not label_tag:
        return ""

    curr = label_tag.next_sibling
    while curr:
        if curr.name == "br":
            break
        
        if isinstance(curr, NavigableString):
            text = curr.string
            # Check for the separator that indicates the next field
            if " - " in text:
                # Value might be before the separator (e.g. "? - ")
                val = text.split(" - ")[0].strip()
                if val and val not in [":", ""]:
                    return val
                break # Hit separator, stop looking
            
            clean = text.strip()
            # If it's actual text and not just a colon or empty
            if clean and clean not in [":", "-"]:
                return clean

        elif curr.name == "a":
            return curr.get_text(strip=True)
        
        curr = curr.next_sibling
    
    return ""


def extract_list(soup, label_text):
    """
    Extracts comma-separated values (e.g., Hair Color: Black, Brown).
    Returns a comma-separated string.
    """
    label_tag = soup.find("b", string=lambda t: t and label_text in t)
    if not label_tag:
        return ""

    values = []
    curr = label_tag.next_sibling
    
    while curr:
        if curr.name == "br":
            break

        if isinstance(curr, NavigableString):
            text = curr.string
            # Stop if we hit the next section separator
            if " - " in text:
                # Check if there is a value before the dash (rare for lists, but possible)
                part = text.split(" - ")[0].strip()
                if part and part != ",":
                    values.append(part)
                break
            
            clean = text.strip()
            # Capture text values (like "?") but ignore comma delimiters
            if clean and clean != "," and clean not in [":"]:
                values.append(clean)

        elif curr.name == "a":
            values.append(curr.get_text(strip=True))

        curr = curr.next_sibling

    return ", ".join(values)


def parse_idol_profile(html, slug):
    soup = BeautifulSoup(html, "html.parser")

    # 1. Check for 404 Body Class
    if soup.body and "error404" in soup.body.get("class", []):
        return None

    # 2. Name & Basic Info
    h1 = soup.find("h1", class_="idol-name")
    full_name = h1.get_text(strip=True).replace("- JAV Profile", "").strip() if h1 else ""

    jp_name = extract_value(soup, "JP:")
    dob = extract_value(soup, "DOB:")
    
    # 3. New Fields
    debut = extract_value(soup, "Debut:")
    birthplace = extract_value(soup, "Birthplace:")
    sign = extract_value(soup, "Sign:")
    blood = extract_value(soup, "Blood:")
    shoe_size = extract_value(soup, "Shoe Size:")
    
    # 4. Multi-value Fields
    hair_length = extract_list(soup, "Hair Length(s):")
    hair_color = extract_list(soup, "Hair Color(s):")

    # 5. Body Stats
    cup = extract_value(soup, "Cup:")
    
    # Height (Clean "156 cm" -> "156")
    height_raw = extract_value(soup, "Height:")
    height = re.sub(r"\D", "", height_raw)

    # Measurements (Split "86-57-87" -> Bust, Waist, Hip)
    measurements = extract_value(soup, "Measurements:")
    bust = waist = hip = ""
    if measurements and "-" in measurements:
        parts = measurements.split("-")
        if len(parts) == 3:
            bust, waist, hip = parts

    # 6. Social Media (Twitter)
    twitter_handle = ""
    twitter_icon = soup.find("i", class_="fa-square-twitter")
    if twitter_icon and twitter_icon.parent and twitter_icon.parent.name == 'a':
        href = twitter_icon.parent.get("href", "")
        if "twitter.com" in href or "x.com" in href:
            parts = href.strip("/").split("/")
            twitter_handle = parts[-1]

    # Return structured object
    return {
        "slug": slug,
        "name": full_name,
        "jpName": jp_name,
        "birthday": dob,
        "debut": debut,
        "birthplace": birthplace,
        "sign": sign,
        "blood_type": blood,
        "shoe_size": shoe_size,
        "hair_length": hair_length,
        "hair_color": hair_color,
        "height": height,
        "cup": cup,
        "bust": bust,
        "waist": waist,
        "hip": hip,
        "twitter": twitter_handle,
        "source_url": f"{BASE_URL}{slug}/"
    }


def process_slug(slug):
    global processed_count
    
    # URL Construction
    url = f"{BASE_URL}{slug}/"
    
    # Polite delay
    time.sleep(random.uniform(0.5, 1.5))

    try:
        resp = session.get(url, timeout=15)
        
        if resp.status_code == 200:
            data = parse_idol_profile(resp.text, slug)
            
            if data:
                save_profile_data(data)
                append_history(slug)
                with console_lock:
                    processed_count += 1
                    print(f"[{processed_count}/{total_tasks}] ✅ Upgraded: {slug}")
            else:
                append_history(slug)
                with console_lock:
                    processed_count += 1
                    print(f"[{processed_count}/{total_tasks}] ❌ 404 (Soft): {slug}")
        
        elif resp.status_code == 404:
            append_history(slug)
            with console_lock:
                processed_count += 1
                print(f"[{processed_count}/{total_tasks}] ❌ 404 (Http): {slug}")
        
        else:
            with console_lock:
                print(f"   ⚠️ Status {resp.status_code}: {slug}")

    except Exception as e:
        with console_lock:
            print(f"   ⚠️ Error processing {slug}: {e}")


def main():
    global total_tasks

    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: {INPUT_FILE} not found. Run compile_targets.py first.")
        return

    print("📖 Loading targets...")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        all_slugs = [line.strip() for line in f if line.strip()]

    history = load_history()
    slugs_to_scrape = [s for s in all_slugs if s not in history]
    
    total_tasks = len(slugs_to_scrape)
    
    print(f"🎯 Targets: {len(all_slugs)}")
    print(f"⏭️  Already Scraped: {len(history)}")
    print(f"🚀 Remaining to Scrape: {total_tasks}")
    print("-" * 50)

    if total_tasks == 0:
        print("Nothing to scrape!")
        return

    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    active_futures = set()

    try:
        for slug in slugs_to_scrape:
            # Queue control to prevent RAM overload
            if len(active_futures) >= MAX_QUEUE_SIZE:
                done, active_futures = wait(active_futures, return_when=FIRST_COMPLETED)

            future = executor.submit(process_slug, slug)
            active_futures.add(future)

        # Wait for remainder
        while active_futures:
            done, active_futures = wait(active_futures, return_when=FIRST_COMPLETED)

    except KeyboardInterrupt:
        print("\n🛑 Interrupted! Saving progress...")
        executor.shutdown(wait=False, cancel_futures=True)
        os._exit(0)

    executor.shutdown(wait=True)
    print("-" * 50)
    print(f"🎉 Done. Data saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()