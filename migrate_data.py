import glob
import json
import os
from app.core.database import Database

def migrate():
    print("Initializing Database...")
    Database.init_db()
    
    files = glob.glob(os.path.join("data", "*.json"))
    print(f"Found {len(files)} JSON files.")
    
    count = 0
    for fpath in files:
        fname = os.path.basename(fpath)
        if fname in ["bulk_products.json", "scraped_data.json"]:
            continue
            
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Extract code from filename
            code = int(fname.split('.')[0])
            
            Database.save_product(code, data)
            count += 1
            if count % 100 == 0:
                print(f"Migrated {count} files...", flush=True)
                
        except Exception as e:
            print(f"Failed to migrate {fname}: {e}")

    print(f"Migration complete. {count} files imported into SQLite.")

if __name__ == "__main__":
    migrate()
