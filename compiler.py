import csv
import glob
import json
import os

# --- CONFIGURATION ---
INPUT_PATTERN = "05/api_batch_*.json"
OUTPUT_FILE = "final_api_data.csv"

CSV_HEADERS = [
    "dvdId",
    "title",
    "jpTitle",
    "releaseDate",
    "duration",
    "generated_url",
    "image",
    "contentId",
    "_id",
]


def main():
    json_files = glob.glob(INPUT_PATTERN)

    # Sort files numerically
    try:
        json_files.sort(key=lambda f: int("".join(filter(str.isdigit, f))))
    except:
        json_files.sort()

    all_data = []
    seen_ids = set()
    existing_count = 0

    # 1. LOAD EXISTING CSV (IF IT EXISTS)
    if os.path.exists(OUTPUT_FILE):
        print(f"🔄 Found existing '{OUTPUT_FILE}'. Loading previous data...")
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Use _id if available, otherwise contentId
                    uid = row.get("_id") or row.get("contentId")
                    if uid:
                        seen_ids.add(uid)
                        all_data.append(row)
                        existing_count += 1
            print(f"   Loaded {existing_count} existing items.")
        except Exception as e:
            print(f"   ⚠️ Could not read existing CSV: {e}")

    if not json_files:
        print("❌ No new JSON files found to merge.")
    else:
        print(f"📂 Found {len(json_files)} JSON files. merging...\n")

    # 2. PROCESS JSON FILES
    total_new = 0
    total_dupes = 0

    for filename in json_files:
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "videos" in data:
                    data = data["videos"]

                file_new = 0

                for item in data:
                    uid = item.get("_id") or item.get("contentId")

                    # 🛡️ DUPLICATE CHECK (Against Old CSV + New JSONs)
                    if uid in seen_ids:
                        total_dupes += 1
                    else:
                        seen_ids.add(uid)

                        clean_row = {
                            "dvdId": item.get("dvdId", ""),
                            "title": item.get("title", ""),
                            "jpTitle": item.get("jpTitle", ""),
                            "releaseDate": item.get("releaseDate", ""),
                            "duration": item.get("duration", 0),
                            "image": item.get("image", ""),
                            "contentId": item.get("contentId", ""),
                            "_id": item.get("_id", ""),
                            "generated_url": f"https://javtrailers.com/video/{item.get('contentId', '')}",
                        }
                        all_data.append(clean_row)
                        file_new += 1
                        total_new += 1

                print(f"   {filename}: +{file_new} New items added")

        except Exception as e:
            print(f"❌ Error reading {filename}: {e}")

    # 3. SAVE EVERYTHING
    if all_data:
        print("\n" + "=" * 40)
        print(
            f"📝 Saving Total {len(all_data)} items ({existing_count} Old + {total_new} New)..."
        )

        try:
            with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as csvfile:
                writer = csv.DictWriter(
                    csvfile, fieldnames=CSV_HEADERS, extrasaction="ignore"
                )
                writer.writeheader()
                writer.writerows(all_data)

            print(f"🎉 SUCCESS! Updated: {OUTPUT_FILE}")
            print(f"🗑️ Skipped {total_dupes} duplicates.")
            print("=" * 40)

        except IOError as e:
            print(f"❌ Error writing CSV: {e}")


if __name__ == "__main__":
    main()
