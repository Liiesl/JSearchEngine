import csv
import json
import os
import time
import datetime
import secrets  # For secure random generation
from tqdm import tqdm

# --- CONFIGURATION ---
CSV_FILE = "final_api_data.csv"
JSONL_FILE = os.path.join("scraped_data", "scraped_data.jsonl")

# Final headers in Lowercase
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

def normalize_id(id_val):
    """Standardizes IDs for comparison (lowercase, stripped)."""
    if not id_val:
        return None
    return str(id_val).strip().lower()

def clean_str(val):
    """Safely converts None/Null to empty string."""
    if val is None:
        return ""
    return str(val).strip()

def generate_dated_oid(date_str, existing_ids):
    """
    Generates a MongoDB-style 24-char ObjectID.
    """
    # 1. Determine Timestamp
    try:
        # Try parsing "YYYY-MM-DD"
        if not date_str:
            raise ValueError("Empty date")
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        timestamp = int(dt.timestamp())
    except (ValueError, TypeError):
        # Fallback to current time if date is missing or invalid
        timestamp = int(time.time())

    # 2. Convert to 8-char Hex
    hex_timestamp = hex(timestamp)[2:].zfill(8)

    # 3. Generate Random Suffix until Unique
    while True:
        # Generate 16 random hex chars (8 bytes)
        random_suffix = secrets.token_hex(8)
        new_oid = f"{hex_timestamp}{random_suffix}"

        # 4. Check Uniqueness
        if new_oid not in existing_ids:
            existing_ids.add(new_oid) # Reserve this ID immediately
            return new_oid

def main():
    # --- 1. LOAD EXISTING CSV DATA ---
    all_rows = []
    
    # lookup_map: Matches video content (dvdid -> row index)
    lookup_map = {}
    
    # used_ids_set: Keeps track of ALL _id strings to prevent duplicates
    used_ids_set = set()
    
    print(f"📖 Loading existing data from {CSV_FILE}...")
    
    if os.path.exists(CSV_FILE):
        try:
            with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                
                for index, row in enumerate(reader):
                    # Clean keys to lowercase
                    clean_row = {k.lower().strip(): v for k, v in row.items()}
                    all_rows.append(clean_row)
                    
                    # Track IDs
                    dvd_id = normalize_id(clean_row.get("dvdid"))
                    content_id = normalize_id(clean_row.get("contentid"))
                    oid = clean_row.get("_id")

                    if dvd_id: lookup_map[dvd_id] = index
                    if content_id: lookup_map[content_id] = index
                    if oid: used_ids_set.add(oid)

        except Exception as e:
            print(f"⚠️ Error reading CSV: {e}")
            return

    print(f"✅ Loaded {len(all_rows)} existing entries.")

    # --- 2. PROCESS SCRAPED JSONL ---
    if not os.path.exists(JSONL_FILE):
        print(f"❌ File not found: {JSONL_FILE}")
        return

    updated_count = 0
    new_count = 0
    
    print(f"🚀 Processing scraped data from {JSONL_FILE}...")
    
    try:
        with open(JSONL_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

            for line in tqdm(lines, desc="Merging"):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    
                    # Normalize Identifiers
                    json_dvd_id = normalize_id(entry.get("dvdId"))
                    json_content_id = normalize_id(entry.get("contentId"))
                    
                    # --- CHECK FOR DUPLICATES ---
                    match_index = -1
                    if json_dvd_id and json_dvd_id in lookup_map:
                        match_index = lookup_map[json_dvd_id]
                    elif json_content_id and json_content_id in lookup_map:
                        match_index = lookup_map[json_content_id]
                    
                    # --- ACTION ---
                    if match_index > -1:
                        # 🔄 UPDATE EXISTING
                        # Use clean_str to handle explicit Nulls in JSON
                        new_actresses = clean_str(entry.get("actress_names"))
                        if new_actresses:
                            all_rows[match_index]["actress_names"] = new_actresses
                            updated_count += 1
                    else:
                        # 🆕 ADD NEW ENTRY
                        release_date = clean_str(entry.get("releaseDate"))
                        
                        new_oid = generate_dated_oid(release_date, used_ids_set)

                        # Logic: .get("key") or "" ensures that if value is None, we get ""
                        new_row = {
                            "dvdid": clean_str(entry.get("dvdId")),
                            "title": clean_str(entry.get("title")),
                            "jptitle": clean_str(entry.get("jpTitle")), # Safely handles missing/null JP title
                            "actress_names": clean_str(entry.get("actress_names")), # Safely handles missing/null actress
                            "releasedate": release_date,
                            "duration": entry.get("duration", 0),
                            "generated_url": clean_str(entry.get("generated_url")),
                            "image": clean_str(entry.get("image")),
                            "contentid": clean_str(entry.get("contentId")),
                            "_id": new_oid
                        }
                        
                        # Add to DB
                        new_index = len(all_rows)
                        all_rows.append(new_row)
                        
                        # Update lookups
                        if json_dvd_id: lookup_map[json_dvd_id] = new_index
                        if json_content_id: lookup_map[json_content_id] = new_index
                        
                        new_count += 1

                except json.JSONDecodeError:
                    continue

    except Exception as e:
        print(f"Error processing JSONL: {e}")

    # --- 3. SAVE RESULTS ---
    print(f"\n💾 Saving to {CSV_FILE}...")
    print(f"   - Updated Actresses: {updated_count}")
    print(f"   - New Videos Added: {new_count}")
    print(f"   - Total DB Size: {len(all_rows)}")

    try:
        with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_rows)
        print("🎉 Done successfully.")
    except Exception as e:
        print(f"❌ Error saving CSV: {e}")

if __name__ == "__main__":
    main()