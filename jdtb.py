import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
INPUT_URLS_FILE = "movie_links.json"
OUTPUT_DIR = "scraped_data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "scraped_data.jsonl")
LOG_FILE = "scraped_history.txt"
MAX_WORKERS = 2
# Limit the queue size to prevent RAM explosion.
# 10 is a safe buffer: keeps threads busy but doesn't load 500k items into RAM.
MAX_QUEUE_SIZE = MAX_WORKERS * 5

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


def load_scraped_history():
    if not os.path.exists(LOG_FILE):
        return set()
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)


def append_to_history(url):
    with file_lock:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(url + "\n")


def save_video_immediate(video_data):
    with file_lock:
        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(video_data, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())


def parse_movie_details(html_content, url):
    soup = BeautifulSoup(html_content, "html.parser")

    def get_value_by_label(label_text):
        label_tag = soup.find("b", string=lambda t: t and label_text in t)
        if label_tag:
            parent_text = label_tag.parent.get_text()
            return parent_text.replace(label_tag.get_text(), "").strip()
        return ""

    title_raw = get_value_by_label("Title:")
    dvd_id = get_value_by_label("DVD ID:")
    content_id = get_value_by_label("Content ID:")
    release_date = get_value_by_label("Release Date:")
    runtime_str = get_value_by_label("Runtime:")

    try:
        duration = int(re.search(r"\d+", runtime_str).group())
    except:
        duration = 0

    actress_list = []
    idol_label = soup.find("b", string=lambda t: t and "Idol" in t)
    if idol_label:
        parent_p = idol_label.parent
        for link in parent_p.find_all("a"):
            name = link.get_text().strip()
            if name:
                actress_list.append(name)

    image_url = ""
    if content_id:
        image_url = (
            f"https://pics.dmm.co.jp/digital/video/{content_id}/{content_id}pl.jpg"
        )

    video_obj = {
        "dvdId": dvd_id,
        "title": title_raw,
        "jpTitle": "",
        "actress_names": ", ".join(actress_list),
        "actress_list": actress_list,
        "releaseDate": release_date,
        "duration": duration,
        "generated_url": url,
        "image": image_url,
        "contentId": content_id,
        "_id": content_id or dvd_id,
    }

    return video_obj


def process_single_url(link):
    global processed_count
    # Tiny jitter
    time.sleep(random.uniform(0.1, 0.4))

    try:
        m_resp = session.get(link, timeout=20)

        if m_resp.status_code == 200:
            video_data = parse_movie_details(m_resp.text, link)

            if video_data.get("dvdId"):
                save_video_immediate(video_data)
                append_to_history(link)

                with console_lock:
                    processed_count += 1
                    print(
                        f"[{processed_count}/{total_tasks}] ✅ Saved: {video_data['dvdId']}"
                    )
            else:
                append_to_history(link)
                with console_lock:
                    processed_count += 1
                    print(
                        f"[{processed_count}/{total_tasks}] ⚠️ Skipped (No Data): {link}"
                    )

        elif m_resp.status_code == 404:
            append_to_history(link)
            with console_lock:
                processed_count += 1
                print(f"[{processed_count}/{total_tasks}] ❌ 404 Not Found: {link}")
        else:
            with console_lock:
                print(f"   ⚠️ Status {m_resp.status_code}: {link}")

    except Exception as e:
        # Pass on error
        pass

    # Return nothing, we don't need to keep results in memory
    return None


def main():
    global total_tasks

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    if not os.path.exists(INPUT_URLS_FILE):
        print(f"❌ Error: {INPUT_URLS_FILE} not found.")
        return

    print("Loading URLs...")
    # Loading 500k strings into a list takes some RAM (~50-100MB),
    # but it is usually acceptable. The Executor queue was the real killer.
    with open(INPUT_URLS_FILE, "r", encoding="utf-8") as f:
        all_urls = json.load(f)

    scraped_history = load_scraped_history()

    # We use a generator expression or just filter manually in the loop
    # to avoid creating another massive list in memory if possible.
    # However, to get a 'total count', we do the list comp.
    urls_to_scrape = [u for u in all_urls if u not in scraped_history]

    # Clear memory of the huge initial load
    del all_urls
    del scraped_history

    total_tasks = len(urls_to_scrape)

    print(f"Remaining: {total_tasks}")
    print(f"Threads: {MAX_WORKERS}")
    print("------------------------------------------------")
    print("Press Ctrl+C to stop safely.")

    if total_tasks == 0:
        print("Nothing to scrape!")
        return

    start_time = time.time()

    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    active_futures = set()

    try:
        for url in urls_to_scrape:
            # OPTIMIZATION:
            # If we have too many active tasks, wait for one to finish
            # before adding a new one. This keeps the queue small.
            if len(active_futures) >= MAX_QUEUE_SIZE:
                done, active_futures = wait(active_futures, return_when=FIRST_COMPLETED)
                # 'done' futures are automatically removed from active_futures by logic,
                # but we catch exceptions here to ensure memory is freed
                for future in done:
                    try:
                        future.result()  # This re-raises exceptions from the thread if any
                    except Exception:
                        pass

            # Submit new task
            future = executor.submit(process_single_url, url)
            active_futures.add(future)

        # After loop finishes, wait for the remaining tasks in the buffer
        while active_futures:
            done, active_futures = wait(active_futures, return_when=FIRST_COMPLETED)

    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted! Stopping immediately...")
        executor.shutdown(wait=False, cancel_futures=True)
        os._exit(0)

    executor.shutdown(wait=True)

    duration = time.time() - start_time
    print("------------------------------------------------")
    print(f"🎉 All done! Processed {total_tasks} links in {duration:.2f} seconds.")


if __name__ == "__main__":
    main()
