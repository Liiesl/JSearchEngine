import csv
import json
import os
import re
from collections import defaultdict
from tqdm import tqdm

# --- CONFIGURATION ---
INPUT_FILE = "final_api_data.csv"
OUTPUT_FILE = "id_structure.json"

# Regex to capture "PREFIX" and "NUMBER"
# Handles: SSNI-123, ssni 123, ipx001
# NEW: Allow alphanumeric prefixes
ID_PATTERN = re.compile(r'^([a-zA-Z0-9]+)[-_ ]?(\d+)$')

def get_ranges(numbers):
    """
    Converts a set of integers into a list of string ranges.
    Example: {1, 2, 3, 5, 6} -> ["001-003", "005-006"]
    """
    if not numbers:
        return []

    sorted_nums = sorted(list(numbers))
    ranges = []
    
    start = sorted_nums[0]
    prev = sorted_nums[0]

    for num in sorted_nums[1:]:
        if num == prev + 1:
            # Consecutive number, extend current range
            prev = num
        else:
            # Gap detected, close previous range
            ranges.append(format_range(start, prev))
            start = num
            prev = num
    
    # Close the final range
    ranges.append(format_range(start, prev))
    return ranges

def format_range(start, end):
    """
    Formats numbers to 3-digit padding (standard JAV format).
    """
    # If it's a single number range (e.g. 5-5), formatting relies on preference.
    # The user requested specific range format: "009-567"
    if start == end:
        return f"{start:03d}-{start:03d}"
    return f"{start:03d}-{end:03d}"

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: {INPUT_FILE} not found.")
        return

    print(f"📂 Reading {INPUT_FILE}...")
    
    # Structure: { "SSNI": {1, 2, 3...}, "IPX": {100, 101...} }
    temp_storage = defaultdict(set)
    
    try:
        with open(INPUT_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            
            for row in tqdm(reader, desc="Parsing IDs"):
                dvd_id = row.get("dvdid", "").strip()
                if not dvd_id:
                    continue

                # match regex
                match = ID_PATTERN.match(dvd_id)
                if match:
                    prefix = match.group(1).upper() # Standardize prefix to UPPERCASE
                    try:
                        number = int(match.group(2))
                        temp_storage[prefix].add(number)
                    except ValueError:
                        continue

    except Exception as e:
        print(f"❌ Error processing CSV: {e}")
        return

    print(f"⚙️  Calculating ranges for {len(temp_storage)} prefixes...")

    final_output = {}

    for prefix, nums in temp_storage.items():
        # Only include prefixes that have a meaningful amount of data (optional)
        if len(nums) > 0:
            range_list = get_ranges(nums)
            final_output[prefix] = {
                "count": len(nums),
                "numeral": range_list
            }

    print(f"💾 Saving to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2)

    print("✅ Done.")

if __name__ == "__main__":
    main()