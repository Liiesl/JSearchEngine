import csv
import os

INPUT_FILE = "final_api_data.csv"


def validate_csv():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ File {INPUT_FILE} not found.")
        return

    print(f"🔍 Scanning {INPUT_FILE}...\n")

    issues = 0
    empty_count = 0

    with open(INPUT_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 1):
            actress_str = row.get("actress_names", "").strip()

            # CHECK 1: EMPTY NAMES
            if not actress_str:
                # print(f"⚠️ [Row {i}] No actress found for: {row.get('title')[:30]}...")
                empty_count += 1
                continue

            names = [n.strip() for n in actress_str.split(", ") if n.strip()]

            # CHECK 2: DUPLICATES
            if len(names) != len(set(names)):
                print(f"⚠️ [Row {i}] Duplicate names: {actress_str}")
                issues += 1

            # CHECK 3: SUBSTRINGS
            for a in names:
                for b in names:
                    if a != b and a in b:
                        print(f"⚠️ [Row {i}] Redundant: '{a}' inside '{b}'")
                        issues += 1
                        break

    print("-" * 30)
    print(f"Total Rows Scanned: {i}")
    print(f"Rows with NO actress: {empty_count} (Normal if actress not in DB)")
    print(f"Rows with Logic Errors: {issues}")

    if issues == 0:
        print("\n✅ Logic is Valid (No dupes/redundancies).")
    else:
        print("\n❌ Issues found.")


if __name__ == "__main__":
    validate_csv()
