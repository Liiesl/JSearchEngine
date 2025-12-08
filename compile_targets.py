import csv
import json
import os
import re
from collections import Counter
from tqdm import tqdm

# --- CONFIGURATION ---
CSV_FILE = "final_api_data.csv"
PROFILE_DB_FILE = "final_actress_profiles.json"
OUTPUT_FILE = "upgrade_targets.txt"
MIN_MOVIE_COUNT = 20

def normalize_name(name):
    """Standardize for matching."""
    if not name:
        return ""
    return name.lower().strip()

def is_duplicate_slug(slug):
    """
    Checks if a slug ends in a hyphen followed by digits (e.g., 'name-1', 'name-2').
    Returns True if it looks like a duplicate postfix.
    """
    return re.search(r'-\d+$', slug) is not None

def determine_tier(profile):
    """
    Calculates the content tier (Same logic as search.py).
    Tier 0: Basic info only (No Avatar).
    Tier 1: Has Avatar.
    Tier 2: Has Avatar + Extra Stats.
    Tier 3: Has Avatar + CastWiki.
    """
    if not profile.get("avatar"):
        return 0
    
    # Check for Wiki (Tier 3)
    if profile.get("castWiki") and isinstance(profile["castWiki"], dict):
        return 3

    # Check for Extra Stats (Tier 2)
    tier_2_keys = ["birthday", "blood_type", "bust", "waist", "hip", "cup", "twitter", "height"]
    stats_count = sum(1 for k in tier_2_keys if profile.get(k))
    
    if stats_count >= 1:
        return 2

    return 1

def main():
    print(f"🚀 Starting Target Compiler (Threshold: {MIN_MOVIE_COUNT}+ movies, Tier 1 or 2 only)...")

    # --- 1. LOAD MOVIE COUNTS ---
    if not os.path.exists(CSV_FILE):
        print(f"❌ Error: {CSV_FILE} not found.")
        return

    actress_counts = Counter()
    print(f"📊 Counting movies in {CSV_FILE}...")
    
    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in tqdm(reader, desc="Scanning CSV"):
            raw_names = row.get("actress_names", "")
            if not raw_names:
                continue
            
            # Split comma-separated names
            names = raw_names.split(",")
            for name in names:
                clean = normalize_name(name)
                if clean:
                    actress_counts[clean] += 1

    # --- 2. LOAD PROFILES ---
    if not os.path.exists(PROFILE_DB_FILE):
        print(f"❌ Error: {PROFILE_DB_FILE} not found. Cannot determine Tiers.")
        return

    print(f"📖 Loading profiles from {PROFILE_DB_FILE}...")
    with open(PROFILE_DB_FILE, "r", encoding="utf-8") as f:
        profiles = json.load(f)

    # --- 3. FILTER AND SELECT ---
    targets = []
    skipped_postfix = 0
    skipped_tier = 0
    skipped_count = 0

    for profile in tqdm(profiles, desc="Filtering Actresses"):
        slug = profile.get("slug")
        name = profile.get("name")
        
        if not slug or not name:
            continue

        # CHECK 1: Remove duplicate postfixes (e.g. 'name-1')
        if is_duplicate_slug(slug):
            skipped_postfix += 1
            continue

        # CHECK 2: Determine Tier (Must be 1 or 2)
        tier = determine_tier(profile)
        if tier == 3:
            # Already has wiki
            skipped_tier += 1
            continue
        if tier == 0:
            # Skip entries that are too broken (no avatar) if you only want Tier 1/2
            skipped_tier += 1
            continue

        # CHECK 3: Popularity Count
        norm_name = normalize_name(name)
        count = actress_counts.get(norm_name, 0)
        
        if count >= MIN_MOVIE_COUNT:
            targets.append(slug)
        else:
            skipped_count += 1

    # --- 4. OUTPUT ---
    targets.sort()
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for slug in targets:
            f.write(slug + "\n")

    print("\n" + "=" * 40)
    print("🏁 COMPILATION COMPLETE")
    print("=" * 40)
    print(f"Total Profiles Scanned: {len(profiles)}")
    print(f"Skipped (Tier 3 or Tier 0): {skipped_tier}")
    print(f"Skipped (Postfix -1, etc):  {skipped_postfix}")
    print(f"Skipped (< {MIN_MOVIE_COUNT} movies):      {skipped_count}")
    print("-" * 40)
    print(f"✅ TARGETS FOUND:        {len(targets)}")
    print(f"💾 Saved to:             {OUTPUT_FILE}")
    print("=" * 40)

if __name__ == "__main__":
    main()