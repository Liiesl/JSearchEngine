import os
import shutil

import lancedb
import pandas as pd

# --- CONFIGURATION ---
DB_FOLDER = "jav_search_index"
BACKUP_FOLDER = "jav_search_index_BACKUP"
TABLE_NAME = "videos"


def migrate_database():
    if not os.path.exists(DB_FOLDER):
        print(f"❌ Database folder '{DB_FOLDER}' not found.")
        return

    print("🛡️ Creating backup of existing database...")
    if os.path.exists(BACKUP_FOLDER):
        shutil.rmtree(BACKUP_FOLDER)
    shutil.copytree(DB_FOLDER, BACKUP_FOLDER)
    print(f"✅ Backup created at: {BACKUP_FOLDER}")

    print("🔌 Connecting to LanceDB...")
    db = lancedb.connect(DB_FOLDER)

    if TABLE_NAME not in db.table_names():
        print(f"❌ Table '{TABLE_NAME}' not found in database.")
        return

    table = db.open_table(TABLE_NAME)
    print(f"📊 Loaded {len(table)} rows.")

    # 1. Load data into Pandas (Preserves Vectors)
    # This is safe because we are just renaming columns, not changing embeddings
    df = table.to_pandas()

    print("🔍 Current Columns:", list(df.columns))

    # 2. Define Mapping (CamelCase -> lowercase)
    # Based on your previous notebook structure
    rename_map = {
        "dvdId": "dvdid",
        "jpTitle": "jptitle",
        "releaseDate": "releasedate",
        "contentId": "contentid",
        # 'title', 'image', 'generated_url', 'actress_names' are already compliant
        # but we map them just in case
    }

    # 3. Apply Renaming
    df = df.rename(columns=rename_map)

    # Ensure all columns are actually lowercase now
    df.columns = [c.lower() for c in df.columns]

    print("✨ New Columns:", list(df.columns))

    # 4. Overwrite Table
    # We use mode="overwrite" to replace the old schema with the new lowercase one
    print("💾 Overwriting table with new schema...")
    db.create_table(TABLE_NAME, data=df, mode="overwrite")

    print("\n✅ Migration Complete!")
    print(
        f"You can now run 'main.py'. If issues persist, restore from '{BACKUP_FOLDER}'."
    )


if __name__ == "__main__":
    migrate_database()
