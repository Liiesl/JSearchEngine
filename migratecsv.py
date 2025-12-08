import os

# CONFIG
INPUT_FILE = "final_api_data.csv"
OUTPUT_FILE = "final_api_data_fixed.csv"

# The target lowercase header (matching the updated compiler.py)
# Note: encoding='utf-8-sig' handles the BOM if present
NEW_HEADER = "dvdid,title,jptitle,actress_names,releasedate,duration,generated_url,image,contentid,_id\n"

def fix_csv_header():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: {INPUT_FILE} not found.")
        return

    print(f"Processing {INPUT_FILE} (this might take a moment)...")

    try:
        # Open both files - reading one line at a time to save RAM
        with open(INPUT_FILE, "r", encoding="utf-8-sig") as f_in, \
             open(OUTPUT_FILE, "w", encoding="utf-8-sig") as f_out:

            # 1. Read the old header (and ignore it)
            old_header = f_in.readline()
            print(f"🔹 Old Header found: {old_header.strip()}")

            # 2. Write the new lowercase header
            f_out.write(NEW_HEADER)
            print(f"🔸 New Header written: {NEW_HEADER.strip()}")

            # 3. Stream the rest of the file efficiently
            line_count = 0
            for line in f_in:
                f_out.write(line)
                line_count += 1
                if line_count % 100000 == 0:
                    print(f"   Processed {line_count} rows...", end="\r")

        print(f"\n✅ Success! New file saved as: {OUTPUT_FILE}")
        print("You can now rename this file to 'final_api_data.csv' or update your config.")

    except Exception as e:
        print(f"\n❌ An error occurred: {e}")

if __name__ == "__main__":
    fix_csv_header()