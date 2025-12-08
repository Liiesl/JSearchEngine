import csv
import glob
import json
import os
from collections import Counter

from tqdm import tqdm

# --- CONFIGURATION ---
CSV_FILE = "final_api_data.csv"  # Your compiled movie data
BATCH_PATTERN = "cast/CASTS_batch_*.json"  # Your raw cast scrape files
ACTRESS_DB_FILE = "actress_db.json"  # Your whitelist (optional check)
OUTPUT_FILE = "unified_cast_list.json"  # The file to upload to the browser
MIN_MOVIE_COUNT = 5  # 🟢 THRESHOLD: Only scrape if >= 5 movies


def normalize_name(name):
    """Standardize for matching (lowercase, strip spaces)."""
    if not name:
        return ""
    return name.lower().strip()


def main():
    print(f"🚀 Starting Smart Filter (Threshold: {MIN_MOVIE_COUNT}+ movies)...")

    # --- 1. COUNT APPEARANCES IN CSV ---
    print(f"📊 Analyzing {CSV_FILE} for popularity...")

    actress_counts = Counter()

    try:
        with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in tqdm(reader, desc="Counting Movies"):
                # The compiler script saves names as "Name A, Name B"
                raw_names = row.get("actress_names", "")
                if not raw_names:
                    continue

                # Split by comma and count
                names = raw_names.split(",")
                for name in names:
                    clean = normalize_name(name)
                    if clean and len(clean) > 1:  # Ignore single letter garbage
                        actress_counts[clean] += 1

    except FileNotFoundError:
        print(f"❌ CRITICAL ERROR: {CSV_FILE} not found.")
        return

    # --- 2. DEFINE THE VIP LIST ---
    # Create a set of names that meet the threshold
    vip_names = set()
    dropped_count = 0

    for name, count in actress_counts.items():
        if count >= MIN_MOVIE_COUNT:
            vip_names.add(name)
        else:
            dropped_count += 1

    print(f"⭐ Found {len(vip_names)} 'VIP' actresses (>= {MIN_MOVIE_COUNT} movies).")
    print(f"🗑️ Dropped {dropped_count} obscure actresses.")

    # (Optional) Cross-reference with actress_db.json if you want to be double sure
    if os.path.exists(ACTRESS_DB_FILE):
        print(f"📖 Loading {ACTRESS_DB_FILE} for validation...")
        with open(ACTRESS_DB_FILE, "r", encoding="utf-8") as f:
            db_list = json.load(f)
            db_set = {normalize_name(n) for n in db_list}

        # Intersection: Must be in VIP list AND in DB list
        before_len = len(vip_names)
        vip_names = vip_names.intersection(db_set)
        print(
            f"✅ After validating against DB: {len(vip_names)} remain (removed {before_len - len(vip_names)})."
        )

    # --- 3. MERGE JSON FILES MATCHING VIPs ---
    batch_files = glob.glob(BATCH_PATTERN)
    print(f"📂 Scanning {len(batch_files)} batch files for metadata links...")

    final_list = {}  # Dict for deduplication

    for filename in tqdm(batch_files, desc="Matching Slugs"):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                items = data.get("casts", data) if isinstance(data, dict) else data

                for item in items:
                    raw_name = item.get("name")
                    slug = item.get("slug")

                    if not raw_name or not slug:
                        continue

                    norm = normalize_name(raw_name)

                    # THE CRITICAL CHECK: Is this person in our VIP list?
                    if norm in vip_names:
                        if slug not in final_list:
                            final_list[slug] = {
                                "slug": slug,
                                "name": raw_name,  # Keep original casing
                                "jpName": item.get("jpName", ""),
                                "_id": item.get("_id", ""),
                            }
        except Exception as e:
            print(f"⚠️ Error reading {filename}: {e}")

    # --- 4. SAVE ---
    sorted_output = sorted(final_list.values(), key=lambda x: x["name"])

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted_output, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 30)
    print("🏁 FINAL REPORT")
    print("=" * 30)
    print(f"Unique Actresses in CSV: {len(actress_counts)}")
    print(f"Qualified (5+ movies):   {len(vip_names)}")
    print(f"Matched with Slugs:      {len(final_list)}")
    print(
        f"Missing Slugs:           {len(vip_names) - len(final_list)} (VIPs without scraped cast data)"
    )
    print("=" * 30)
    print(f"💾 File saved to: {OUTPUT_FILE}")
    print("👉 Upload this file to the Console Script.")


if __name__ == "__main__":
    main()
