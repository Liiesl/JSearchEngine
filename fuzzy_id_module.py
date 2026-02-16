# --- START OF FILE fuzzy_id_module.py ---

import re
from difflib import SequenceMatcher
from heapq import nlargest
from typing import List, Tuple, Dict, Any

# --- PERCENTAGE QUOTAS ---
PCT_QUOTA_EXACT_PREFIX = 0.50
PCT_QUOTA_FUZZY_PREFIX = 0.1

KEYBOARD_MAP = {
    '1': 0, '2': 1, '3': 2, '4': 3, '5': 4, '6': 5, '7': 6, '8': 7, '9': 8, '0': 9
}

def parse_arg(arg: str) -> Tuple[str, str, int]:
    """Parses 'SSNI-123' or 'T28-001' into parts."""
    clean_arg = arg.strip().upper()
    
    # OLD: match = re.match(r'^([a-zA-Z]+)[-_ ]?(\d+)$', clean_arg)
    # NEW: Allow Alphanumeric (A-Z, 0-9) in the prefix group
    match = re.match(r'^([a-zA-Z0-9]+)[-_ ]?(\d+)$', clean_arg)
    
    if match:
        return match.group(1), match.group(2), int(match.group(2))
    
    # Check for prefix-only search (e.g. user types "A046G")
    # OLD: match_prefix = re.match(r'^([a-zA-Z]+)', clean_arg)
    match_prefix = re.match(r'^([a-zA-Z0-9]+)', clean_arg)
    
    if match_prefix:
        return match_prefix.group(1), "1", 1
    return "", "", 0

def expand_ranges(ranges: List[str]) -> List[int]:
    """Expands compressed number ranges from the JSON DB."""
    expanded = []
    for r in ranges:
        try:
            if "-" in r:
                start_s, end_s = r.split("-")
                expanded.extend(range(int(start_s), int(end_s) + 1))
            else:
                expanded.append(int(r))
        except ValueError:
            continue
    return expanded

def get_keyboard_similarity(s1: str, s2: str) -> float:
    """Calculates physical keyboard distance similarity for numbers."""
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
    """Generates score and metadata for a candidate ID."""
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
        meta.append("N:Exact")
        is_vip = True
    elif typo_score > numeric_sim and typo_score > 0.65:
        meta.append("N:Typo")
        base_score += 0.1
    else:
        meta.append("N:Near")

    # --- Prefix Logic ---
    if prefix_score == 1.0:
        base_score += 0.10
        meta.append("P:Exact")
    elif t_prefix in c_prefix or c_prefix in t_prefix:
        base_score += 0.05
        meta.append("P:Sub")
    else:
        meta.append(f"P:{int(prefix_score*100)}%")

    return base_score, ", ".join(meta), is_vip

def generate_candidates(query: str, db_structure: dict, top_k: int = 20) -> List[Dict[str, Any]]:
    """
    Main entry point. 
    1. Parses the query.
    2. Searches the structural DB for prefixes.
    3. Generates specific ID candidates with scores.
    """
    target_prefix, target_num_str, target_num_int = parse_arg(query)
    if not target_prefix:
        return []

    # --- 1. CALCULATE QUOTAS ---
    limit_exact = max(1, int(top_k * PCT_QUOTA_EXACT_PREFIX))
    limit_fuzzy = max(1, int(top_k * PCT_QUOTA_FUZZY_PREFIX))

    # --- 2. PREFIX SEARCH ---
    prefix_candidates = []
    for db_prefix in db_structure.keys():
        sim = SequenceMatcher(None, target_prefix, db_prefix).ratio()
        if sim > 0.5: 
            prefix_candidates.append((sim, db_prefix))
    
    # Get top 10 matching prefixes to iterate over
    top_prefixes = nlargest(10, prefix_candidates, key=lambda x: x[0])

    # --- 3. CANDIDATE GENERATION ---
    final_pool = []

    for p_score, p_name in top_prefixes:
        data = db_structure[p_name]
        valid_nums = expand_ranges(data.get("numeral", []))
        
        # Optimization: If too many numbers, sort by proximity to target first
        if len(valid_nums) > 5000:
            valid_nums.sort(key=lambda x: abs(x - target_num_int))
            valid_nums = valid_nums[:2000]

        vip_matches = []      
        imperfect_matches = [] 

        for num in valid_nums:
            score, meta, is_vip = calculate_hybrid_score(target_prefix, p_name, target_num_str, num)
            
            if score < 0.4: continue

            # Standardize ID format for the DB query (e.g. ssni-001)
            # Adjust padding based on the number length found in DB logic if needed, 
            # but standard JAV is typically 3 digits padded.
            formatted_id = f"{p_name}-{num:03d}".lower()

            res = {
                "id": formatted_id,
                "score": score,
                "meta": meta,
                "is_vip": is_vip
            }

            if is_vip:
                vip_matches.append(res)
            else:
                imperfect_matches.append(res)
        
        # --- APPLY DYNAMIC QUOTA ---
        final_pool.extend(vip_matches)

        if imperfect_matches:
            imperfect_matches.sort(key=lambda x: x['score'], reverse=True)
            current_limit = limit_exact if p_name == target_prefix else limit_fuzzy
            final_pool.extend(imperfect_matches[:current_limit])

    # 4. Final Global Sort
    top_results = nlargest(top_k, final_pool, key=lambda x: x['score'])
    
    return top_results