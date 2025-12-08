import glob
import json
import os
import re

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
                            "avatar": item.get("avatar", None)
                        })
        except:
            continue

    if not files_found:
        return []

    return exact_matches

def normalize_tier3(profile):
    """
    If the profile has castWiki (Tier 3), extract hidden stats into top-level keys
    so they match the structure of Tier 2 profiles and expose detailed bio info.
    """
    wiki = profile.get("castWiki")
    if not wiki or not isinstance(wiki, dict):
        return profile
    
    # --- 1. Standardize Tier 2 Stats (Height, Birthday, Measurements) ---
    body = wiki.get("body", {})
    personal = wiki.get("personal", {})
    
    # Measurements: "100-55-84 cm" -> bust, waist, hip
    if not profile.get("bust") and body.get("measurements"):
        raw = body["measurements"]
        parts = re.findall(r'\d+', raw)
        if len(parts) >= 3:
            profile["bust"] = parts[0]
            profile["waist"] = parts[1]
            profile["hip"] = parts[2]
            
    # Cup: "J metric" -> "J"
    if not profile.get("cup") and body.get("braCupSize"):
        profile["cup"] = body["braCupSize"].split(' ')[0]

    # Height: "5 ft 2 in (1.57 m)" -> "157"
    if not profile.get("height") and body.get("height"):
        raw_h = body["height"]
        m_metric = re.search(r'\((\d+\.?\d*)\s*m\)', raw_h)
        if m_metric:
            try:
                cm = int(float(m_metric.group(1)) * 100)
                profile["height"] = str(cm)
            except: pass
        elif "cm" in raw_h:
            m_cm = re.search(r'(\d+)', raw_h)
            if m_cm: profile["height"] = m_cm.group(1)
            
    # Birthday: "May 25, 1987\n..." -> "May 25, 1987"
    if not profile.get("birthday") and personal.get("born"):
        profile["birthday"] = personal["born"].split('\n')[0].strip()

    # --- 2. Extract Tier 3 Specific Fields ---
    
    # Personal Section
    if personal.get("alsoKnownAs"): profile["alsoKnownAs"] = personal["alsoKnownAs"]
    if personal.get("yearsActive"): profile["yearsActive"] = personal["yearsActive"]
    if personal.get("ethnicity"): profile["ethnicity"] = personal["ethnicity"]
    if personal.get("nationality"): profile["nationality"] = personal["nationality"]

    # Body Section
    if body.get("boobs"): profile["boobs"] = body["boobs"]
    if body.get("type"): profile["type"] = body["type"]
    if body.get("eyeColor"): profile["eyeColor"] = body["eyeColor"]
    if body.get("hair"): profile["hair"] = body["hair"]
    if body.get("underarmHair"): profile["underarmHair"] = body["underarmHair"]
    if body.get("pubicHair"): profile["pubicHair"] = body["pubicHair"]
        
    return profile

def determine_tier(profile):
    """
    Calculates the content tier of an actress profile.
    Tier 0: Basic info only (No Avatar).
    Tier 1: Has Avatar.
    Tier 2: Has Avatar + Basic Stats (Birthday, Cups, Twitter, etc.).
    Tier 2.5: Has Avatar + Extended Stats (Debut, Sign, Blood, etc.).
    Tier 3: Has Avatar + CastWiki (Detailed bio).
    """
    if not profile.get("avatar"):
        return 0
    
    # Check for Wiki (Tier 3)
    if profile.get("castWiki") and isinstance(profile["castWiki"], dict):
        return 3

    # Check for Extended Stats (Tier 2.5)
    # If any of these "new" keys exist and are not empty/question marks
    tier_2_5_keys = ["debut", "birthplace", "sign", "shoe_size", "hair_length", "hair_color"]
    has_extended = any(profile.get(k) and profile.get(k) != "?" for k in tier_2_5_keys)
    
    if has_extended:
        return 2.5

    # Check for Basic Stats (Tier 2)
    tier_2_keys = ["birthday", "blood_type", "bust", "waist", "hip", "cup", "twitter", "height"]
    stats_count = sum(1 for k in tier_2_keys if profile.get(k))
    
    if stats_count >= 1:
        return 2

    return 1

def find_profile(query):
    """
    Main entry point for the server. 
    Performs search, merges profile, normalizes data, and calculates Tier.
    """
    results = search_all(query)

    if not results:
        return None

    # Sort by slug
    results.sort(key=lambda x: x['slug'])

    # Load profiles
    profile_map = load_profile_db()
    
    # Merge Logic
    final_result = results[0] 
    slug = final_result["slug"]
    
    if slug in profile_map:
        full_profile = profile_map[slug]
        final_result.update(full_profile)
    
    # Normalize nested Wiki data to top-level if needed
    final_result = normalize_tier3(final_result)
    
    # Calculate Tier
    final_result["tier"] = determine_tier(final_result)
        
    return final_result