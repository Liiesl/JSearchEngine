# converter.py
import json

data = []
with open("scraped_data/scraped_data.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        data.append(json.loads(line))

with open("scraped_data/final_complete.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
