import csv
import glob
import json
import os
import re

from tqdm import tqdm

# --- CONFIGURATION ---
VIDEO_PATTERN = "*/api_batch_*.json"
CAST_PATTERN = "cast/CASTS_batch_*.json"
OUTPUT_FILE = "final_api_data.csv"
ACTRESS_LIST_FILE = "actress_db.json"

CSV_HEADERS = [
    "dvdId",
    "title",
    "jpTitle",
    "actress_names",
    "releaseDate",
    "duration",
    "generated_url",
    "image",
    "contentId",
    "_id",
]

# --- STOP WORDS (Ignore these names entirely) ---
# These are actress names that are also common English words or abbreviations.
STOP_WORDS = {
    "an",
    "as",
    "at",
    "by",
    "do",
    "go",
    "he",
    "hi",
    "if",
    "in",
    "is",
    "it",
    "me",
    "my",
    "no",
    "of",
    "on",
    "or",
    "so",
    "to",
    "up",
    "us",
    "we",
    "ai",
    "4k",
    "vr",
    "hd",
    "bd",
    "dvd",
    "rin",
    "ran",
}

# --- NOISE REMOVAL ---
NOISE_PATTERNS = [
    r"\[ai.*?\]",  # [AI Remastered]
    r"\(ai.*?\)",  # (AI)
    r"\【ai.*?\】",  # Japanese brackets
    r"ai remastered",
]


def clean_title_noise(text):
    """Removes [AI] tags so they don't mess up matching."""
    if not text:
        return ""
    text = text.lower()
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, " ", text)
    return text


def normalize_text(text):
    """
    Standardizes text.
    'Honami Takasaka's' -> ' honami takasaka s '
    """
    if not text:
        return " "

    text = text.lower()
    # Replace apostrophes with space explicitly first
    text = text.replace("'", " ")
    # Replace anything not a-z or 0-9 with space
    text = re.sub(r"[^a-z0-9]", " ", text)
    # Collapse spaces
    text = re.sub(r"\s+", " ", text).strip()
    return f" {text} "


def parse_actress_aliases(name_entry):
    clean_entry = name_entry.strip().strip(",")
    parts = re.split(r"[(),]", clean_entry)

    display_name = parts[0].strip()
    search_terms = []

    for part in parts:
        raw_part = part.strip()
        norm = normalize_text(raw_part).strip()  # Remove padding for check

        # 1. Skip if length is too short (1 letter)
        if len(norm) < 2:
            continue

        # 2. Skip if it is a Stop Word
        if norm in STOP_WORDS:
            continue

        search_terms.append(f" {norm} ")  # Add padding back for matching

    return display_name, search_terms


def main():
    # --- 1. LOAD CAST DATABASE ---
    print("💃 Loading Cast Database...")
    cast_files = glob.glob(CAST_PATTERN)

    processed_actresses = []

    for c_file in tqdm(cast_files, desc="Reading Cast Files"):
        try:
            with open(c_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                items = data.get("casts", data) if isinstance(data, dict) else data

                for item in items:
                    raw_name = item.get("name") if isinstance(item, dict) else item
                    if raw_name:
                        display, terms = parse_actress_aliases(raw_name)
                        if terms:
                            processed_actresses.append(
                                {"display": display, "terms": terms}
                            )
        except Exception as e:
            print(f"⚠️ Error reading {c_file}: {e}")

    # Sort by Name Length (Longest First) - CRITICAL for Deduplication
    processed_actresses.sort(key=lambda x: len(x["display"]), reverse=True)
    print(f"✅ Loaded {len(processed_actresses)} actress profiles.")

    # --- 2. LOAD EXISTING CSV ---
    all_data = []
    seen_ids = set()

    if os.path.exists(OUTPUT_FILE):
        print(f"🔄 Loading existing '{OUTPUT_FILE}'...")
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    uid = row.get("_id") or row.get("contentId")
                    if uid:
                        seen_ids.add(uid)
                    all_data.append(row)
        except Exception:
            all_data = []

    # --- 3. PROCESS NEW VIDEOS ---
    json_files = glob.glob(VIDEO_PATTERN)
    total_new = 0

    for filename in tqdm(json_files, desc="Processing Batches"):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                videos = data.get("videos", data) if isinstance(data, dict) else data

                for item in videos:
                    uid = item.get("_id") or item.get("contentId")
                    if not uid or uid in seen_ids:
                        continue
                    seen_ids.add(uid)

                    # --- MATCHING ---
                    raw_title = item.get("title", "")
                    cleaned_title = clean_title_noise(raw_title)
                    target_title = normalize_text(cleaned_title)

                    matches = []

                    if len(target_title) > 5:
                        for actress in processed_actresses:
                            # Check aliases
                            for term in actress["terms"]:
                                if term in target_title:
                                    matches.append(actress["display"])
                                    break

                    # --- DEDUPLICATION (The Fix) ---
                    # Matches are already sorted longest first (e.g., Reiko Sawamura, Reiko)
                    final_names = []

                    for candidate in matches:
                        # Convert to lower for comparison
                        cand_lower = candidate.lower()

                        # Check if this candidate is inside any name we already kept
                        is_substring = False
                        for kept in final_names:
                            if cand_lower in kept.lower():
                                is_substring = True
                                break

                        if not is_substring:
                            final_names.append(candidate)

                    actress_str = ", ".join(final_names)

                    clean_row = {
                        "dvdId": item.get("dvdId", ""),
                        "title": raw_title,
                        "jpTitle": item.get("jpTitle", ""),
                        "actress_names": actress_str,
                        "releaseDate": item.get("releaseDate", ""),
                        "duration": item.get("duration", 0),
                        "image": item.get("image", ""),
                        "contentId": item.get("contentId", ""),
                        "_id": item.get("_id", ""),
                        "generated_url": f"https://javtrailers.com/video/{item.get('contentId', '')}",
                    }
                    all_data.append(clean_row)
                    total_new += 1

        except Exception as e:
            tqdm.write(f"❌ Error: {e}")

    # --- 4. SAVE ---
    if total_new > 0:
        print(f"\n📝 Saving {len(all_data)} items...")
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.DictWriter(
                csvfile, fieldnames=CSV_HEADERS, extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(all_data)
        print("🎉 Done.")
    else:
        print("\n✅ Up to date.")

    # Save simple DB
    unique_names = list(set([a["display"] for a in processed_actresses]))
    with open(ACTRESS_LIST_FILE, "w", encoding="utf-8") as f:
        json.dump(unique_names, f)


if __name__ == "__main__":
    main()
