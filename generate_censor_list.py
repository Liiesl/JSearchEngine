import csv
import json
import os
import re
import unicodedata
from tqdm import tqdm

# --- CONFIGURATION ---
INPUT_FILE = "final_api_data.csv"
OUTPUT_MARKDOWN = "censored_words_edit.md"
OUTPUT_MAPPING_JSON = "censored_mapping.json"

TARGET_COLS = ["title"] 

# Regex: Matches alphanumeric strings containing 2 or more asterisks.
CENSOR_PATTERN = re.compile(r"[a-zA-Z0-9_]*\*{2,}[a-zA-Z0-9_]*")

def normalize_text(text):
    if not text: return ""
    text = unicodedata.normalize('NFKD', text)
    return text.encode('ascii', 'ignore').decode('utf-8')

def get_contextual_key(text, match_obj):
    """
    Constructs a key based on the word itself or its surroundings 
    if it is purely stars.
    """
    token = match_obj.group()
    start_idx, end_idx = match_obj.span()

    # 1. If the token contains letters (e.g. "S***t"), just use it.
    if any(c.isalnum() for c in token):
        return token

    # 2. It is pure stars. Capture surrounding context precisely.
    
    # Grab text before the stars
    pre_chunk = text[:start_idx]
    # Find the last chunk of non-whitespace characters immediately before
    prev_match = re.search(r"(\S+\s*)$", pre_chunk)
    prefix = prev_match.group(0) if prev_match else ""

    # Grab text after the stars
    post_chunk = text[end_idx:]
    # Find the first chunk of non-whitespace characters immediately after
    next_match = re.search(r"^(\s*\S+)", post_chunk)
    suffix = next_match.group(0) if next_match else ""

    # Combine exact spacing
    context_key = f"{prefix}{token}{suffix}"
    
    return context_key

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: {INPUT_FILE} not found.")
        return

    print(f"🔍 Scanning {INPUT_FILE}...")

    word_groups = {}
    
    with open(INPUT_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        
        for row_idx, row in tqdm(enumerate(reader), desc="Processing", unit="row"):
            
            for col_name in TARGET_COLS:
                original_text = row.get(col_name, "")
                if "*" not in original_text: continue

                clean_text = normalize_text(original_text)
                matches = list(CENSOR_PATTERN.finditer(clean_text))
                
                if matches:
                    dvd_id = row.get("dvdId", "N/A")
                    image = row.get("image", "")

                    for match_obj in matches:
                        final_key = get_contextual_key(clean_text, match_obj)
                        
                        # Fallback for weird edge cases
                        if final_key not in clean_text:
                            final_key = match_obj.group() 

                        if final_key not in word_groups:
                            word_groups[final_key] = {
                                "locations": [],
                                "example_dvd": dvd_id,
                                "example_img": image,
                                "example_context": clean_text
                            }
                        
                        word_groups[final_key]["locations"].append({
                            "row": row_idx,
                            "col": col_name
                        })

    # --- SAVE JSON ---
    print(f"💾 Saving mapping to {OUTPUT_MAPPING_JSON}...")
    with open(OUTPUT_MAPPING_JSON, "w", encoding="utf-8") as f:
        json.dump(word_groups, f, indent=2)

    # --- GENERATE MARKDOWN ---
    print(f"📝 Generating {OUTPUT_MARKDOWN}...")
    
    sorted_keys = sorted(word_groups.keys(), key=lambda x: x.lower())

    with open(OUTPUT_MARKDOWN, "w", encoding="utf-8") as f:
        f.write("# Censored Words Review\n\n")
        f.write("| Censored Key | Replacement | Hits | Ref | Context Title |\n")
        f.write("|---|---|---|---|---|\n")

        for key in sorted_keys:
            data = word_groups[key]
            
            img_md = f"[Img]({data['example_img']})" if data['example_img'] else ""
            dvd_ref = f"{data['example_dvd']} {img_md}"
            
            # Escape pipes to prevent table breakage
            safe_key = key.replace("|", "/")
            safe_context = data['example_context'].replace("|", "/")
            
            # --- CHANGE IS HERE ---
            # Removed the logic that did: if len > 60 then truncate.
            # Now it prints the full string.
            
            count = len(data['locations'])

            f.write(f"| `{safe_key}` |  | {count} | {dvd_ref} | {safe_context} |\n")

    print("🎉 Done! Full titles are now visible.")

if __name__ == "__main__":
    main()