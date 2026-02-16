#!/usr/bin/env python3
"""Extract and group DVDID prefixes by fuzzy similarity."""

import csv
from difflib import SequenceMatcher
from collections import defaultdict

def similar(a, b, threshold=0.7):
    """Check if two strings are similar enough."""
    return SequenceMatcher(None, a, b).ratio() >= threshold

def main():
    # Extract unique prefixes
    print("Extracting prefixes...")
    prefixes = set()
    
    with open('final_api_data.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            dvd_id = row.get('dvdid', '')
            if '-' in dvd_id:
                prefix = dvd_id.split('-')[0].lower().strip()
                if prefix and len(prefix) > 1:  # Skip single char prefixes
                    prefixes.add(prefix)
    
    prefixes = sorted(list(prefixes))
    print(f"Found {len(prefixes)} unique prefixes")
    
    # Group by fuzzy similarity
    print("Grouping by similarity...")
    groups = []
    used = set()
    
    for prefix in prefixes:
        if prefix in used:
            continue
        
        # Start new group with this prefix
        group = [prefix]
        used.add(prefix)
        
        # Find similar prefixes
        for other in prefixes:
            if other not in used and similar(prefix, other):
                group.append(other)
                used.add(other)
        
        groups.append(sorted(group))
    
    # Sort groups by size (largest first) and then alphabetically
    groups.sort(key=lambda g: (-len(g), g[0]))
    
    # Write output
    print("Writing to dvdid_prefixes.txt...")
    with open('dvdid_prefixes.txt', 'w', encoding='utf-8') as f:
        for i, group in enumerate(groups):
            for prefix in group:
                f.write(prefix + '\n')
            f.write('\n')  # Empty line between groups
    
    print(f"Done! Created {len(groups)} groups")

if __name__ == '__main__':
    main()
