import json
import os
import shutil
import re

# --- CONFIGURATION ---
ORIGINAL_DB_FILE = "final_actress_profiles.json"
NEW_SCRAPE_FILE = "scraped_profiles.jsonl"
OUTPUT_FILE = "final_actress_profiles.json"

def is_valid_data(value):
    """
    Determines if a value is 'real' data or just scraper garbage.
    Handles:
      - None
      - "N/A", "n/a"
      - "?"
      - "?\t\t\t\t-" (Tabs, dashes, mixed garbage)
      - "?, ?"
    """
    if value is None:
        return False
    
    s = str(value).strip()
    
    # 1. Check for specific text-based nulls
    if s.lower() in ["n/a", "unknown", "none"]:
        return False

    # 2. Check if the string contains ANY alphanumeric character.
    # If a string is composed ENTIRELY of symbols (?, -, ,, \t, whitespace), it is invalid.
    # This handles "?\t\t\t\t-" and "?, ?" automatically.
    if not re.search(r'[a-zA-Z0-9\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\uff00-\uff9f\u4e00-\u9faf]', s):
        # The regex above looks for: A-Z, 0-9, and Japanese characters (Hiragana, Katakana, Kanji).
        # If NONE of these are found, it's just symbols/garbage.
        return False

    return True

def clean_string(value):
    """
    Optional: Cleans up valid data if it has trailing separator garbage.
    e.g. "Tokyo\t-" -> "Tokyo"
    """
    if not value: return ""
    s = str(value).strip()
    # Remove trailing tabs or dashes that might have been captured
    s = s.strip('\t -')
    return s

def main():
    if not os.path.exists(ORIGINAL_DB_FILE):
        print(f"❌ Error: Original DB {ORIGINAL_DB_FILE} not found.")
        return

    if not os.path.exists(NEW_SCRAPE_FILE):
        print(f"❌ Error: New scrape file {NEW_SCRAPE_FILE} not found.")
        return

    # 1. Create Backup
    backup_file = ORIGINAL_DB_FILE + ".bak"
    shutil.copy2(ORIGINAL_DB_FILE, backup_file)
    print(f"💾 Backup created: {backup_file}")

    # 2. Load Original DB
    print("📖 Loading original database...")
    with open(ORIGINAL_DB_FILE, "r", encoding="utf-8") as f:
        original_list = json.load(f)

    # Convert list to dict for O(1) access
    db_map = {item["slug"]: item for item in original_list if "slug" in item}
    print(f"   Loaded {len(db_map)} existing profiles.")

    # 3. Load New Scrape Data
    print("📖 Loading new scraped data...")
    new_entries = []
    with open(NEW_SCRAPE_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                new_entries.append(json.loads(line))
    print(f"   Loaded {len(new_entries)} new updates.")

    # 4. Merge Logic
    updated_count = 0
    fields_added_count = 0

    merge_keys = [
        "debut", 
        "birthplace", 
        "sign", 
        "blood_type", 
        "shoe_size", 
        "hair_length", 
        "hair_color", 
        "twitter",
        "cup",
        "height",
        "bust", 
        "waist", 
        "hip"
    ]

    for new_item in new_entries:
        slug = new_item.get("slug")
        if not slug or slug not in db_map:
            continue

        target = db_map[slug]
        entry_modified = False

        for key in merge_keys:
            raw_new_val = new_item.get(key)
            existing_val = target.get(key)

            # Check validity
            is_new_valid = is_valid_data(raw_new_val)
            is_old_valid = is_valid_data(existing_val)

            # RULE: Prioritize Original.
            # Merge ONLY if:
            # 1. New data IS valid (contains actual text/numbers)
            # 2. Old data IS NOT valid (is empty, null, or garbage)
            if is_new_valid and not is_old_valid:
                # Clean the new value before saving (removes trailing dashes etc)
                final_val = clean_string(raw_new_val)
                if final_val: # Check again after cleaning
                    target[key] = final_val
                    entry_modified = True
                    fields_added_count += 1
        
        if entry_modified:
            updated_count += 1

    # 5. Save
    final_list = list(db_map.values())

    print("-" * 40)
    print(f"✅ Merging complete.")
    print(f"   Profiles Updated: {updated_count}")
    print(f"   Total Fields Filled: {fields_added_count}")
    print(f"   Total Profiles: {len(final_list)}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_list, f, ensure_ascii=False, indent=2)

    print(f"💾 Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()