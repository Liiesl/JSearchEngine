import csv
import json
import os

# --- CONFIGURATION ---
EXISTING_CSV = "final_api_data.csv"
NEW_DATA_JSONL = os.path.join("scraped_data", "scraped_data.jsonl")


def load_existing_ids(csv_file):
    """
    Loads all unique identifiers (_id, dvdid, contentid) from the compiler CSV
    into a set for fast lookup.
    """
    existing_ids = set()

    if not os.path.exists(csv_file):
        return existing_ids

    try:
        with open(csv_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # CHANGED: Reading lowercase keys from compiled CSV
                if row.get("_id"):
                    existing_ids.add(row["_id"].strip())
                if row.get("dvdid"):
                    existing_ids.add(row["dvdid"].strip())
                if row.get("contentid"):
                    existing_ids.add(row["contentid"].strip())
    except Exception as e:
        print(f"Error reading CSV: {e}")

    return existing_ids


def main():
    existing_db = load_existing_ids(EXISTING_CSV)

    total_entries = 0
    new_entries = 0
    duplicate_entries = 0

    if os.path.exists(NEW_DATA_JSONL):
        try:
            with open(NEW_DATA_JSONL, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                        total_entries += 1

                        # Source JSONL still has camelCase keys
                        check_ids = [
                            entry.get("_id"),
                            entry.get("dvdId"),
                            entry.get("contentId"),
                        ]

                        # Check if ANY of the IDs exist in the CSV database
                        is_duplicate = False
                        for cid in check_ids:
                            if cid and str(cid).strip() in existing_db:
                                is_duplicate = True
                                break

                        if is_duplicate:
                            duplicate_entries += 1
                        else:
                            new_entries += 1

                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error reading JSONL: {e}")
    else:
        print(f"File not found: {NEW_DATA_JSONL}")

    # --- OUTPUT ---
    print(f"total of entries: {total_entries}")
    print(f"detected new enteries: {new_entries}")
    print(f"duplicated enteries: {duplicate_entries}")


if __name__ == "__main__":
    main()