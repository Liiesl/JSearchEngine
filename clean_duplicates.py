import json
import os
import re
import shutil
from tqdm import tqdm

# --- CONFIGURATION ---
INPUT_FILE = "final_actress_profiles.json"
BACKUP_FILE = "final_actress_profiles.backup.json"

def get_base_slug(slug):
    """
    Extracts the base slug from a postfixed one.
    'yua-mikami-1' -> 'yua-mikami'
    'yua-mikami'   -> 'yua-mikami'
    """
    if not slug:
        return ""
    # Regex checks for hyphen followed by digits at the end of string
    match = re.search(r'^(.*)-\d+$', slug)
    if match:
        return match.group(1)
    return slug

def determine_tier(profile):
    """
    Calculates content tier.
    Tier 3: Wiki, Tier 2: Stats, Tier 1: Avatar, Tier 0: Junk
    """
    if not profile.get("avatar"):
        return 0
    
    # Tier 3: Has Wiki
    if profile.get("castWiki") and isinstance(profile["castWiki"], dict):
        return 3

    # Tier 2: Has Extra Stats
    tier_2_keys = ["birthday", "blood_type", "bust", "waist", "hip", "cup", "twitter", "height"]
    stats_count = sum(1 for k in tier_2_keys if profile.get(k))
    
    if stats_count >= 1:
        return 2

    return 1

def main():
    print("🚀 Starting Smart Deduplication...")

    # --- 1. SAFETY CHECK & BACKUP ---
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: {INPUT_FILE} not found.")
        return

    print(f"📦 Creating backup at {BACKUP_FILE}...")
    shutil.copy(INPUT_FILE, BACKUP_FILE)

    # --- 2. LOAD DATA ---
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # --- 3. GROUPING ---
    # Dictionary structure: { "base-slug": [profile1, profile2, ...] }
    groups = {}
    
    print(f"🧩 Grouping {len(data)} profiles by base slug...")
    for profile in data:
        slug = profile.get("slug")
        if not slug: 
            continue
            
        base = get_base_slug(slug)
        if base not in groups:
            groups[base] = []
        groups[base].append(profile)

    # --- 4. SELECTION TOURNAMENT ---
    final_list = []
    stats = {
        "kept_original": 0,
        "upgraded_from_postfix": 0,
        "removed_duplicates": 0,
        "total_processed": 0
    }

    for base_slug, candidates in tqdm(groups.items(), desc="Resolving Conflicts"):
        stats["total_processed"] += 1
        
        # If only one candidate exists, keep it (but ensure name is clean)
        if len(candidates) == 1:
            winner = candidates[0]
            # Edge case: If the only file is 'name-1', rename it to 'name'
            if winner["slug"] != base_slug:
                winner["slug"] = base_slug
                stats["upgraded_from_postfix"] += 1
            else:
                stats["kept_original"] += 1
            final_list.append(winner)
            continue

        # --- CONFLICT RESOLUTION ---
        # We have multiple candidates (e.g., 'name', 'name-1').
        # We need to score them to find the best one.
        
        scored_candidates = []
        for p in candidates:
            tier = determine_tier(p)
            is_perfect_slug = (p["slug"] == base_slug)
            # Tuple for sorting: (Tier Score, Is It The Original Slug?, The Object)
            # We prioritize Tier first. If Tiers are equal, we prioritize the one 
            # that already has the correct slug to avoid unnecessary renaming.
            scored_candidates.append((tier, is_perfect_slug, p))

        # Sort Descending: Higher Tier first, True (1) slug second.
        scored_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)

        # The Winner is index 0
        winner_tier, _, winner_profile = scored_candidates[0]
        
        # Calculate how many we are deleting
        stats["removed_duplicates"] += (len(candidates) - 1)

        # --- APPLY WINNER LOGIC ---
        # Ensure the winner takes the "Base Slug" name
        if winner_profile["slug"] != base_slug:
            # We are promoting a post-fixed profile (e.g. name-1 is Tier 2) 
            # over the original (name was Tier 1)
            winner_profile["slug"] = base_slug
            stats["upgraded_from_postfix"] += 1
        else:
            stats["kept_original"] += 1

        final_list.append(winner_profile)

    # --- 5. SAVE ---
    # Sort alphabetically by slug for neatness
    final_list.sort(key=lambda x: x["slug"])

    with open(INPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_list, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 40)
    print("🏁 CLEANUP COMPLETE")
    print("=" * 40)
    print(f"Original Count:      {len(data)}")
    print(f"Final Count:         {len(final_list)}")
    print(f"🗑️  Removed Duplicates: {stats['removed_duplicates']}")
    print(f"✨ Upgraded/Renamed:   {stats['upgraded_from_postfix']} (Found better data in postfix)")
    print("=" * 40)
    print(f"💾 Overwrote: {INPUT_FILE}")
    print(f"🛡️  Backup at: {BACKUP_FILE}")

if __name__ == "__main__":
    main()