import argparse
import glob
import json
import sys
import os
import textwrap

# --- CONFIGURATION ---
BATCH_PATTERN = "cast/CASTS_batch_*.json"
PROFILE_DB_FILE = "final_actress_profiles.json" 

def normalize(text):
    if not text:
        return ""
    return text.lower().strip()

def load_profile_db():
    if not os.path.exists(PROFILE_DB_FILE):
        return {}
    try:
        with open(PROFILE_DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {
                item.get("slug"): item 
                for item in data 
                if isinstance(item, dict) and "slug" in item
            }
    except Exception:
        return {}

def search_all(query):
    norm_query = normalize(query)
    files = glob.iglob(BATCH_PATTERN)
    
    exact_matches = []
    seen_slugs = set()
    files_found = False

    for filepath in files:
        files_found = True
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                items = data.get("casts", data) if isinstance(data, dict) else data
                if not isinstance(items, list): continue

                for item in items:
                    raw_name = item.get("name", "")
                    slug = item.get("slug", "")
                    
                    if not raw_name or not slug: continue
                    if slug in seen_slugs: continue

                    if normalize(raw_name) == norm_query:
                        seen_slugs.add(slug)
                        # Basic Match Data
                        exact_matches.append({
                            "slug": slug,
                            "name": raw_name,
                            "jpName": item.get("jpName", "N/A"),
                            "id": item.get("_id", ""),
                            "link": item.get("link", ""),
                            # Tier 1 defaults (might be overwritten by profile DB later)
                            "avatar": item.get("avatar", None)
                        })
        except:
            continue

    if not files_found:
        print(f"❌ Error: No files found in '{BATCH_PATTERN}'", file=sys.stderr)
        sys.exit(1)

    return exact_matches

def print_details(data):
    """
    Intelligent printer that handles Tier 0, 1, 2, and 3 data structures.
    """
    wrapper = textwrap.TextWrapper(initial_indent="      ", subsequent_indent="      ", width=80)
    
    # --- Check Tier Level for display label ---
    has_wiki = "castWiki" in data and isinstance(data["castWiki"], dict)
    has_stats = any(k in data for k in ["birthday", "blood_type", "bust", "waist", "hip", "height", "twitter"])
    has_avatar = "avatar" in data and data["avatar"]

    tier = 0
    if has_avatar: tier = 1
    if has_stats: tier = 2
    if has_wiki: tier = 3

    print(f"📌 SLUG: {data.get('slug')}  |  JP: {data.get('jpName')}  |  ID: {data.get('id') or data.get('_id')}  |  [TIER {tier}]")

    # --- TIER 1: Avatar ---
    if has_avatar:
        print(f"   📸 Avatar: {data['avatar']}")

    # --- TIER 2: Basic Stats & Socials ---
    if has_stats:
        print("   📊 Stats:")
        
        # Format Measurements (B-W-H)
        b = data.get('bust', '?')
        w = data.get('waist', '?')
        h = data.get('hip', '?')
        cup = data.get('cup', '') # Sometimes implied in data
        
        measure_str = f"B{b}"
        if cup: measure_str += f"({cup})"
        measure_str += f" - W{w} - H{h}"
        
        details = []
        if data.get('height'): details.append(f"Height: {data['height']}cm")
        if data.get('birthday'): details.append(f"Born: {data['birthday']}")
        if data.get('blood_type'): details.append(f"Blood: {data['blood_type']}")
        
        print(f"      {measure_str}")
        if details:
            print(f"      {'  |  '.join(details)}")

        # Socials
        if data.get('twitter'):
            print(f"      🐦 Twitter: @{data['twitter']}")
        if data.get('hobby'):
             print(f"      🎮 Hobby: {data['hobby']}")

    # --- TIER 3: Detailed Wiki ---
    if has_wiki:
        wiki = data['castWiki']
        print("   📖 Wiki Profile:")
        
        # 1. Wiki Description
        desc = wiki.get('description', '')
        if desc:
            # Handle newlines in description properly by splitting paragraphs
            for paragraph in desc.split('\n'):
                if paragraph.strip():
                    print(wrapper.fill(paragraph))
                    print("") # Space between paragraphs

        # 2. Personal Info Section (Wiki Nested Dict)
        personal = wiki.get('personal', {})
        if personal:
            print("      👤 Personal Details:")
            for key, val in personal.items():
                if key not in ['_id', '__v']:
                    # Clean up camelCase keys for display (e.g. alsoKnownAs -> Also Known As)
                    clean_key = ''.join([' '+c if c.isupper() else c for c in key]).strip().title()
                    val_clean = str(val).replace('\n', ', ') # Keep single line
                    print(f"         • {clean_key}: {val_clean}")

        # 3. Body Info Section (Wiki Nested Dict)
        body = wiki.get('body', {})
        if body:
            print("      💃 Physical Details (Wiki Source):")
            for key, val in body.items():
                if key not in ['_id', '__v']:
                    clean_key = key.replace('braCupSize', 'Cup').title()
                    print(f"         • {clean_key}: {val}")

    # --- Tier 0 fallback (implied) ---
    if not has_avatar and not has_stats and not has_wiki:
        print("      (No detailed profile available)")

    print("-" * 75)

def main():
    parser = argparse.ArgumentParser(description="Find actress slugs and display detailed profiles.")
    parser.add_argument("query", type=str, help="Actress name (e.g., 'Airi')")
    parser.add_argument("--json", action="store_true", help="Output as JSON array")
    # Removed --profile flag; profile loading is now default
    args = parser.parse_args()

    results = search_all(args.query)

    if not results:
        print(f"❌ No matches found for '{args.query}'", file=sys.stderr)
        sys.exit(1)

    results.sort(key=lambda x: x['slug'])

    # Always load profiles
    profile_map = load_profile_db()
    
    # Warn if DB is missing (only in text mode)
    if not profile_map and not args.json:
        # Check if it was because file didn't exist
        if not os.path.exists(PROFILE_DB_FILE):
             print(f"⚠️ Warning: '{PROFILE_DB_FILE}' not found. Showing basic results only.", file=sys.stderr)

    # Attach profile data
    final_results = []
    for res in results:
        slug = res["slug"]
        if slug in profile_map:
            # MERGE STRATEGY: 
            # Take the basic batch result, and update it with the full profile DB object.
            # This ensures we get top-level stats (Tier 2) and castWiki (Tier 3).
            full_profile = profile_map[slug]
            res.update(full_profile)
        final_results.append(res)

    if args.json:
        print(json.dumps(final_results, indent=2, ensure_ascii=False))
    else:
        print(f"🔎 Found {len(final_results)} matches for '{args.query}':\n")
        print("-" * 75)
        for res in final_results:
            print_details(res)

if __name__ == "__main__":
    main()