import csv
import shutil
import os
import json
import datetime
from tqdm import tqdm

# --- CONFIGURATION ---
INPUT_CSV = "final_api_data.csv"
MARKDOWN_SOURCE = "censored_words_edit.md"
JSON_MAPPING = "censored_mapping.json"
TARGET_COL = "title"

def create_backup(filename):
    """Creates a timestamped copy of the file."""
    if not os.path.exists(filename):
        return False
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    root, ext = os.path.splitext(filename)
    backup_name = f"{root}_backup_{timestamp}{ext}"
    try:
        shutil.copy2(filename, backup_name)
        print(f"📦 Backup created: {backup_name}")
        return True
    except Exception as e:
        print(f"❌ Failed to create backup: {e}")
        return False

def load_json_map(json_file):
    if not os.path.exists(json_file):
        print(f"⚠️ JSON map {json_file} not found. Falling back to text search?")
        return None
    with open(json_file, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_markdown_corrections(md_file):
    """
    Parses the markdown table to extract {key: replacement}.
    """
    corrections = {}
    if not os.path.exists(md_file):
        print(f"❌ Error: {md_file} not found.")
        return {}

    print(f"📖 Reading corrections from {md_file}...")
    with open(md_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "---" in line or "Censored Key" in line:
            continue
        
        parts = line.split("|")
        if len(parts) < 3:
            continue

        raw_key = parts[1].strip().strip("`")
        replacement = parts[2].strip()

        if replacement:
            # Handle the slash escape from generator
            real_key = raw_key.replace("/", "|")
            corrections[real_key] = replacement

    return corrections

def main():
    # 1. Load Data
    corrections = parse_markdown_corrections(MARKDOWN_SOURCE)
    if not corrections:
        print("⚠️ No corrections found. Exiting.")
        return

    mapping_data = load_json_map(JSON_MAPPING)
    if not mapping_data:
        print("❌ Missing JSON mapping. Cannot perform precise merge.")
        return

    # 2. Build Efficient Lookup: Row Index -> List of (Key, Replacement)
    # We invert the data so we know exactly what to do for each row.
    row_instructions = {}

    print("⚙️  Mapping corrections to specific rows...")
    mapped_count = 0
    
    for key, replacement in corrections.items():
        if key in mapping_data:
            # Get specific locations from JSON
            locations = mapping_data[key]["locations"]
            for loc in locations:
                r_idx = int(loc["row"])
                if r_idx not in row_instructions:
                    row_instructions[r_idx] = []
                row_instructions[r_idx].append((key, replacement))
                mapped_count += 1
        else:
            print(f"⚠️ Warning: Key '{key}' found in MD but not in JSON map.")

    print(f"✅ Prepared fixes for {len(row_instructions)} specific rows.")

    # 3. Create Backup
    if not create_backup(INPUT_CSV): return

    # 4. Process CSV
    temp_output = "temp_fixed_data.csv"
    updated_rows_count = 0

    try:
        with open(INPUT_CSV, "r", encoding="utf-8-sig") as infile, \
             open(temp_output, "w", encoding="utf-8-sig", newline="") as outfile:
            
            reader = csv.DictReader(infile)
            writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
            writer.writeheader()

            for i, row in tqdm(enumerate(reader), desc="Merging", unit="row"):
                # Check if this row index has instructions
                if i in row_instructions:
                    original_text = row[TARGET_COL]
                    new_text = original_text
                    
                    # Apply specific fixes for this row
                    fixes = row_instructions[i]
                    # Sort by key length descending to avoid partial matches
                    fixes.sort(key=lambda x: len(x[0]), reverse=True)

                    for key, replacement in fixes:
                        if key in new_text:
                            new_text = new_text.replace(key, replacement)
                    
                    if new_text != original_text:
                        row[TARGET_COL] = new_text
                        updated_rows_count += 1
                
                writer.writerow(row)

        os.replace(temp_output, INPUT_CSV)
        print(f"\n🎉 Success! Updated {updated_rows_count} rows using precise JSON mapping.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        if os.path.exists(temp_output):
            os.remove(temp_output)

if __name__ == "__main__":
    main()