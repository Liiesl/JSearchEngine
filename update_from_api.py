import csv
import glob
import json
import os
import re
import shutil
from datetime import datetime
from tqdm import tqdm

# --- CONFIGURATION ---
VIDEO_PATTERN = "*/api_batch_*.json"
CAST_PATTERN = "cast/CASTS_batch_*.json"
OUTPUT_FILE = "final_api_data.csv"
BACKUP_DIR = "backups"
ACTRESS_LIST_FILE = "actress_db.json"

CSV_HEADERS = [
    "dvdid",
    "title",
    "jptitle",
    "actress_names",
    "releasedate",
    "duration",
    "generated_url",
    "image",
    "contentid",
    "_id",
]

# --- STOP WORDS (Ignore these names entirely) ---
STOP_WORDS = {
    "an", "as", "at", "by", "do", "go", "he", "hi", "if", "in", "is", "it",
    "me", "my", "no", "of", "on", "or", "so", "to", "up", "us", "we",
    "ai", "4k", "vr", "hd", "bd", "dvd", "rin", "ran",
}

# --- NOISE REMOVAL ---
NOISE_PATTERNS = [
    r"\[ai.*?\]",
    r"\(ai.*?\)",
    r"\【ai.*?\】",
    r"ai remastered",
]


def get_backup_path():
    """Generate backup file path with today's date."""
    today = datetime.now().strftime("%Y%m%d")
    return os.path.join(BACKUP_DIR, f"{today}_api_data.csv")


def create_backup():
    """Create backup of existing CSV before updating."""
    if not os.path.exists(OUTPUT_FILE):
        print(f"⚠️ No existing {OUTPUT_FILE} to backup.")
        return False
    
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_path = get_backup_path()
    
    # If backup already exists for today, add timestamp
    if os.path.exists(backup_path):
        timestamp = datetime.now().strftime("%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"{datetime.now().strftime('%Y%m%d')}_{timestamp}_api_data.csv")
    
    try:
        shutil.copy2(OUTPUT_FILE, backup_path)
        print(f"✅ Backup created: {backup_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to create backup: {e}")
        return False


def clean_title_noise(text):
    """Removes [AI] tags so they don't mess up matching."""
    if not text:
        return ""
    text = text.lower()
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, " ", text)
    return text


def normalize_text(text):
    """Standardizes text for matching."""
    if not text:
        return " "
    text = text.lower()
    text = text.replace("'", " ")
    text = re.sub(r"[^a-z0-9]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return f" {text} "


def parse_actress_aliases(name_entry):
    """Parse actress name and aliases from cast entry."""
    clean_entry = name_entry.strip().strip(",")
    parts = re.split(r"[(),]", clean_entry)
    display_name = parts[0].strip()
    search_terms = []

    for part in parts:
        raw_part = part.strip()
        norm = normalize_text(raw_part).strip()

        if len(norm) < 2:
            continue
        if norm in STOP_WORDS:
            continue

        search_terms.append(f" {norm} ")

    return display_name, search_terms


def load_actress_database():
    """Load and process actress cast data."""
    print("💃 Loading Cast Database...")
    cast_files = glob.glob(CAST_PATTERN)
    processed_actresses = []

    for c_file in tqdm(cast_files, desc="Reading Cast Files"):
        try:
            with open(c_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                items = data.get("casts", data) if isinstance(data, dict) else data

                for item in items:
                    raw_name = item.get("name") if isinstance(item, dict) else item
                    if raw_name:
                        display, terms = parse_actress_aliases(raw_name)
                        if terms:
                            processed_actresses.append(
                                {"display": display, "terms": terms}
                            )
        except Exception as e:
            print(f"⚠️ Error reading {c_file}: {e}")

    # Sort by Name Length (Longest First) - CRITICAL for Deduplication
    processed_actresses.sort(key=lambda x: len(x["display"]), reverse=True)
    print(f"✅ Loaded {len(processed_actresses)} actress profiles.")
    
    return processed_actresses


def match_actresses_in_title(title, processed_actresses):
    """Match actress names in title."""
    if not title:
        return []
    
    cleaned_title = clean_title_noise(title)
    target_title = normalize_text(cleaned_title)
    
    if len(target_title) <= 5:
        return []
    
    matches = []
    for actress in processed_actresses:
        for term in actress["terms"]:
            if term in target_title:
                matches.append(actress["display"])
                break
    
    # Deduplication - remove substrings
    final_names = []
    for candidate in matches:
        cand_lower = candidate.lower()
        is_substring = False
        for kept in final_names:
            if cand_lower in kept.lower():
                is_substring = True
                break
        if not is_substring:
            final_names.append(candidate)
    
    return final_names


def load_existing_data():
    """Load existing CSV data and return rows + seen IDs."""
    all_data = []
    seen_ids = set()

    if os.path.exists(OUTPUT_FILE):
        print(f"📖 Loading existing '{OUTPUT_FILE}'...")
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Normalize keys to lowercase for consistency
                    clean_row = {k.lower().strip(): v for k, v in row.items()}
                    uid = clean_row.get("_id") or clean_row.get("contentid")
                    if uid:
                        seen_ids.add(uid)
                    all_data.append(clean_row)
        except Exception as e:
            print(f"⚠️ Error loading existing data: {e}")
            all_data = []
    
    print(f"✅ Loaded {len(all_data)} existing entries.")
    return all_data, seen_ids


def process_new_videos(all_data, seen_ids, processed_actresses):
    """Process new API batch files and add to data."""
    json_files = glob.glob(VIDEO_PATTERN)
    total_new = 0
    
    print(f"\n🔍 Found {len(json_files)} batch files to process...")

    for filename in tqdm(json_files, desc="Processing Batches"):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                videos = data.get("videos", data) if isinstance(data, dict) else data

                for item in videos:
                    uid = item.get("_id") or item.get("contentId")
                    if not uid or uid in seen_ids:
                        continue
                    seen_ids.add(uid)

                    # Match actresses
                    raw_title = item.get("title", "")
                    final_names = match_actresses_in_title(raw_title, processed_actresses)
                    actress_str = ", ".join(final_names)

                    clean_row = {
                        "dvdid": item.get("dvdId", ""),
                        "title": raw_title,
                        "jptitle": item.get("jpTitle", ""),
                        "actress_names": actress_str,
                        "releasedate": item.get("releaseDate", ""),
                        "duration": item.get("duration", 0),
                        "image": item.get("image", ""),
                        "contentid": item.get("contentId", ""),
                        "_id": item.get("_id", ""),
                        "generated_url": f"https://javtrailers.com/video/{item.get('contentId', '')}",
                    }
                    all_data.append(clean_row)
                    total_new += 1

        except Exception as e:
            tqdm.write(f"❌ Error processing {filename}: {e}")
    
    return total_new


def save_data(all_data, processed_actresses):
    """Save updated CSV and actress database."""
    print(f"\n📝 Saving {len(all_data)} items to {OUTPUT_FILE}...")
    try:
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.DictWriter(
                csvfile, fieldnames=CSV_HEADERS, extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(all_data)
        print("✅ CSV saved successfully.")
    except Exception as e:
        print(f"❌ Error saving CSV: {e}")
        return False

    # Save actress database
    unique_names = list(set([a["display"] for a in processed_actresses]))
    try:
        with open(ACTRESS_LIST_FILE, "w", encoding="utf-8") as f:
            json.dump(unique_names, f, indent=2)
        print(f"✅ Actress database saved: {len(unique_names)} unique names.")
    except Exception as e:
        print(f"⚠️ Error saving actress database: {e}")
    
    return True


def main():
    print("=" * 60)
    print("🔄 JAV Search Engine - API Update Script")
    print("=" * 60)
    
    # Step 1: Create backup
    print("\n📦 Step 1: Creating backup...")
    create_backup()
    
    # Step 2: Load actress database
    print("\n👥 Step 2: Loading actress database...")
    processed_actresses = load_actress_database()
    
    # Step 3: Load existing data
    print("\n📂 Step 3: Loading existing data...")
    all_data, seen_ids = load_existing_data()
    
    # Step 4: Process new videos
    print("\n🎬 Step 4: Processing new API batches...")
    total_new = process_new_videos(all_data, seen_ids, processed_actresses)
    
    # Step 5: Save results
    print("\n💾 Step 5: Saving updated data...")
    if total_new > 0:
        save_data(all_data, processed_actresses)
        print(f"\n✨ Update complete! Added {total_new} new videos.")
        print(f"   Total database size: {len(all_data)} videos")
    else:
        print("\n✅ No new videos found. Database is up to date.")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
