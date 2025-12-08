import glob
import json
import os

from tqdm import tqdm

# --- CONFIGURATION ---
MASTER_TARGET_FILE = "unified_cast_list.json"  # The list of 5k+ VIPs
DOWNLOADED_PATTERN = (
    "cast/ACTRESS_PROFILES_batch_*.json"  # The files downloaded from browser
)
FINAL_DB_FILE = "final_actress_profiles.json"  # The compiled persistent DB
NEXT_REQUEST_FILE = "cast_list_request.json"  # The file to upload to the browser
BATCH_LIMIT = 500  # 🟢 LIMIT: Only prepare 500 items per run


def load_json(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        # Silent fail for checking existence, or print error
        return []


def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    print("🤖 STARTING WORKFLOW MANAGER (Persistent Mode)")
    print("=" * 30)

    # 1. LOAD THE MASTER TARGET LIST
    if not os.path.exists(MASTER_TARGET_FILE):
        print(f"❌ Error: {MASTER_TARGET_FILE} not found.")
        print("   Run 'filter_and_merge.py' first.")
        return

    master_list = load_json(MASTER_TARGET_FILE)

    # --- NEW STEP: LOAD EXISTING DATABASE ---
    collected_profiles = {}

    if os.path.exists(FINAL_DB_FILE):
        print(f"📖 Loading existing database: {FINAL_DB_FILE}...")
        existing_data = load_json(FINAL_DB_FILE)
        if isinstance(existing_data, list):
            for item in existing_data:
                if isinstance(item, dict):
                    slug = item.get("slug")
                    if slug:
                        collected_profiles[slug] = item
            print(f"   ✅ Loaded {len(collected_profiles)} existing profiles.")
        else:
            print("   ⚠️ Existing DB format invalid. Starting fresh.")
    else:
        print("   🆕 No existing database found. Creating new one.")

    # 2. MERGE NEW BATCH FILES
    profile_files = glob.glob(DOWNLOADED_PATTERN)

    if profile_files:
        print(f"📂 Found {len(profile_files)} new batch files to merge.")

        for p_file in tqdm(profile_files, desc="Merging Batches"):
            data = load_json(p_file)

            # Handle wrapping
            items = data.get("casts", data) if isinstance(data, dict) else data

            if not isinstance(items, list):
                continue

            for item in items:
                if not isinstance(item, dict):
                    continue

                slug = item.get("slug")
                # UPDATE LOGIC: This overwrites old data with new data if slug exists,
                # or adds it if it's new.
                if slug:
                    collected_profiles[slug] = item
    else:
        print("📂 No new batch files found (using existing DB only).")

    # 3. SAVE THE UPDATED DB
    final_db_list = list(collected_profiles.values())
    final_db_list.sort(key=lambda x: x.get("name", ""))

    save_json(FINAL_DB_FILE, final_db_list)
    print(f"💾 Saved Persistent DB: {len(final_db_list)} profiles.")

    # 4. CALCULATE MISSING & SLICE
    missing_items = []
    collected_slugs = set(collected_profiles.keys())

    for target in master_list:
        if target.get("slug") not in collected_slugs:
            missing_items.append(target)

    # TAKE ONLY THE FIRST 500
    next_batch = missing_items[:BATCH_LIMIT]
    remaining_after_this = len(missing_items) - len(next_batch)

    # 5. REPORT & GENERATE
    print("=" * 30)
    print(f"📊 STATUS REPORT")
    print(f"   Target Total:        {len(master_list)}")
    print(f"   Currently in DB:     {len(collected_profiles)}")
    print(f"   Still Missing:       {len(missing_items)}")
    print("-" * 30)
    print(f"   📝 Added to Request: {len(next_batch)}")
    print(f"   💤 Left for later:   {remaining_after_this}")
    print("=" * 30)

    if len(next_batch) == 0:
        print("🎉 CONGRATULATIONS! Work is complete.")
        save_json(NEXT_REQUEST_FILE, [])
    else:
        save_json(NEXT_REQUEST_FILE, next_batch)
        print(f"🚀 GENERATED: {NEXT_REQUEST_FILE}")
        print(f"👉 Upload this file to the browser.")


if __name__ == "__main__":
    main()
