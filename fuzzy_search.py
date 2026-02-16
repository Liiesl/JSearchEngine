import argparse
import json
import re
import sys
import time
from difflib import SequenceMatcher
from heapq import nlargest
from typing import List, Tuple

# --- CONFIG ---
DB_FILE = "id_structure.json"

# --- PERCENTAGE QUOTAS ---
# How much of the total "Top K" can be filled by Imperfect Matches (Neighbors/Typos)?
# VIPs (Exact Number Matches) DO NOT count towards this quota (they are unlimited).
PCT_QUOTA_EXACT_PREFIX = 0.50  # 30% (e.g., 6 slots in Top 20)
PCT_QUOTA_FUZZY_PREFIX = 0.1  # 5%  (e.g., 1 slot in Top 20)

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

KEYBOARD_MAP = {
    '1':0, '2':1, '3':2, '4':3, '5':4, '6':5, '7':6, '8':7, '9':8, '0':9
}

def load_db(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"{Colors.RED}❌ Database file '{path}' not found.{Colors.ENDC}")
        sys.exit(1)

def parse_arg(arg: str) -> Tuple[str, str, int]:
    match = re.match(r'^([a-zA-Z]+)[-_ ]?(\d+)$', arg.strip())
    if match:
        return match.group(1).upper(), match.group(2), int(match.group(2))
    match_prefix = re.match(r'^([a-zA-Z]+)', arg.strip())
    if match_prefix:
        return match_prefix.group(1).upper(), "1", 1
    return "", "", 0

def expand_ranges(ranges: List[str]) -> List[int]:
    expanded = []
    for r in ranges:
        try:
            start_s, end_s = r.split("-")
            expanded.extend(range(int(start_s), int(end_s) + 1))
        except ValueError:
            continue
    return expanded

def get_keyboard_similarity(s1: str, s2: str) -> float:
    if len(s1) != len(s2): return 0.0
    total_dist = 0
    for c1, c2 in zip(s1, s2):
        if c1 == c2: continue
        if c1 not in KEYBOARD_MAP or c2 not in KEYBOARD_MAP:
            total_dist += 9
            continue
        dist = abs(KEYBOARD_MAP[c1] - KEYBOARD_MAP[c2])
        total_dist += dist
    if total_dist == 0: return 1.0
    avg_dist = total_dist / len(s1)
    if avg_dist > 1.2: return 0.0 
    return 1.0 - (avg_dist / 5.0)

def calculate_hybrid_score(t_prefix, c_prefix, t_num_str, c_num_int):
    # 1. Prefix Score
    prefix_score = SequenceMatcher(None, t_prefix, c_prefix).ratio()
    if prefix_score < 0.4: return 0.0, "Mismatch", False

    c_num_str = str(c_num_int)
    t_num_padded = t_num_str.zfill(len(c_num_str))

    # 2. Number Analysis
    # A. Numeric Proximity
    try:
        diff = abs(int(t_num_str) - c_num_int)
        numeric_sim = 1.0 / (1.0 + (diff * 0.2))
    except:
        numeric_sim = 0.0

    # B. String/Typo Analysis
    visual_sim = SequenceMatcher(None, t_num_padded, c_num_str).ratio()
    physical_sim = get_keyboard_similarity(t_num_padded, c_num_str)
    
    typo_score = visual_sim
    if len(t_num_padded) == len(c_num_str):
        if physical_sim == 0.0 and visual_sim < 0.8:
            typo_score = 0.0 
    
    best_num_score = max(typo_score, numeric_sim)
    
    # 3. Categorization
    base_score = (prefix_score * 0.5) + (best_num_score * 0.5)
    meta = []
    is_vip = False 

    # --- Number Logic ---
    if best_num_score == 1.0:
        base_score += 0.35 
        meta.append("N:Exact++")
        is_vip = True
    elif typo_score > numeric_sim and typo_score > 0.65:
        meta.append("N:Typo")
        base_score += 0.1
    else:
        meta.append("N:Near")

    # --- Prefix Logic ---
    if prefix_score == 1.0:
        base_score += 0.10
        meta.append("P:Exact+")
    elif t_prefix in c_prefix or c_prefix in t_prefix:
        base_score += 0.05
        meta.append("P:Sub")
    else:
        meta.append(f"P:{int(prefix_score*100)}%")

    return base_score, ", ".join(meta), is_vip

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dvd_id", help="e.g., ssni-123")
    parser.add_argument("--top-k", type=int, default=20)
    args = parser.parse_args()

    start_time = time.perf_counter()
    db = load_db(DB_FILE)
    
    target_prefix, target_num_str, target_num_int = parse_arg(args.dvd_id)
    if not target_prefix:
        sys.exit(1)

    print(f"{Colors.HEADER}🔍 Searching: {Colors.BOLD}{target_prefix}-{target_num_str}{Colors.ENDC}")

    # --- 1. CALCULATE QUOTAS ---
    # Convert percentages to integer slots
    # Ensure Fuzzy limit is at least 1, unless top-k is tiny
    limit_exact = max(1, int(args.top_k * PCT_QUOTA_EXACT_PREFIX))
    limit_fuzzy = max(1, int(args.top_k * PCT_QUOTA_FUZZY_PREFIX))

    # 2. Prefix Search (Get more candidates to ensure diversity fills the list)
    prefix_candidates = []
    for db_prefix in db.keys():
        sim = SequenceMatcher(None, target_prefix, db_prefix).ratio()
        if sim > 0.5: prefix_candidates.append((sim, db_prefix))
    
    top_prefixes = nlargest(10, prefix_candidates, key=lambda x: x[0])

    # 3. Candidate Generation
    final_pool = []

    for p_score, p_name in top_prefixes:
        data = db[p_name]
        valid_nums = expand_ranges(data["numeral"])
        
        if len(valid_nums) > 5000:
            valid_nums.sort(key=lambda x: abs(x - target_num_int))
            valid_nums = valid_nums[:2000]

        vip_matches = []      
        imperfect_matches = [] 

        for num in valid_nums:
            score, meta, is_vip = calculate_hybrid_score(target_prefix, p_name, target_num_str, num)
            
            if score < 0.4: continue

            res = {
                "id": f"{p_name}-{num:03d}",
                "score": score,
                "meta": meta
            }

            if is_vip:
                vip_matches.append(res)
            else:
                imperfect_matches.append(res)
        
        # --- APPLY DYNAMIC QUOTA ---
        
        # 1. VIPs are Free
        final_pool.extend(vip_matches)

        # 2. Imperfects are Limited
        if imperfect_matches:
            imperfect_matches.sort(key=lambda x: x['score'], reverse=True)
            
            current_limit = limit_exact if p_name == target_prefix else limit_fuzzy
            
            final_pool.extend(imperfect_matches[:current_limit])

    # 4. Final Global Sort
    top_results = nlargest(args.top_k, final_pool, key=lambda x: x['score'])
    elapsed = time.perf_counter() - start_time

    # 5. Display
    print(f"\n{Colors.GREEN}Found {len(top_results)} matches in {elapsed:.4f}s:{Colors.ENDC}\n")
    print(f"{'RANK':<5} {'ID':<15} {'SCORE':<10} {'DETAILS'}")
    print("-" * 65)
    
    for i, res in enumerate(top_results, 1):
        score_display = f"{res['score']:.4f}"
        meta = res['meta']
        
        color = Colors.ENDC
        if "N:Exact++" in meta:
            if "P:Exact+" in meta: color = Colors.GREEN + Colors.BOLD
            elif "P:Sub" in meta: color = Colors.CYAN + Colors.BOLD
            else: color = Colors.CYAN
        elif "N:Typo" in meta:
            color = Colors.YELLOW
            
        print(f"{i:<5} {color}{res['id']:<15}{Colors.ENDC} {score_display:<10} {Colors.BLUE}[{meta}]{Colors.ENDC}")

if __name__ == "__main__":
    main()