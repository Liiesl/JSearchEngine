import json
import re
import time
import os
from contextlib import asynccontextmanager
from typing import List, Optional
from difflib import SequenceMatcher

import lancedb
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sentence_transformers import SentenceTransformer

# --- IMPORT LOCAL MODULE ---
import search as search_engine

# --- CONFIG ---
DB_FOLDER = "jav_search_index"
TABLE_NAME = "videos"
MODEL_NAME = "intfloat/multilingual-e5-large"
ACTRESS_DB_FILE = "actress_db.json"

# --- GLOBAL RESOURCES ---
resources = {}


class Timer:
    def __init__(self, name):
        self.name = name
        self.start = 0

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.perf_counter() - self.start
        print(f"⏱️ [{self.name}] took {elapsed:.4f}s")

def normalize_text(text):
    if not text:
        return ""
    return text.lower().strip()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load resources on startup
    print("⚡ Loading Neural Model & Database...")
    resources["model"] = SentenceTransformer(MODEL_NAME)

    try:
        db = lancedb.connect(DB_FOLDER)
        resources["table"] = db.open_table(TABLE_NAME)
        print(f"📚 Index connected: {len(resources['table'])} videos")
    except Exception as e:
        print(f"❌ Database error: {e}")
        resources["table"] = None

    # Load Actress Names for entity extraction
    try:
        with open(ACTRESS_DB_FILE, "r", encoding="utf-8") as f:
            actress_list = json.load(f)
            actress_list.sort(key=len, reverse=True)
            resources["actress_db"] = actress_list
            print(f"💃 Actress DB loaded: {len(actress_list)} names")
    except FileNotFoundError:
        resources["actress_db"] = []
        print("⚠️ Actress DB not found.")

    yield
    resources.clear()

app = FastAPI(lifespan=lifespan)


# --- HELPER LOGIC ---
def is_dvd_id(query):
    q = query.strip()
    return re.match(r"^[a-zA-Z]+[- ]?\d+$", q) is not None


def extract_entities(user_query, actress_db):
    cleaned_query = user_query.lower()
    tokens = user_query.strip().split()
    found_actresses = []

    # --- PHASE 1: Fuzzy Priority for 2-Word Inputs ---
    # We prioritize matching 2-word inputs against Multi-Word actresses (e.g. "Hikaru Nag" -> "Hikaru Nagi")
    # This prevents "Hikaru" (single word) from being eagerly exact-matched first.
    if len(tokens) == 2:
        input_name = user_query.lower()
        reversed_name = f"{tokens[1]} {tokens[0]}".lower()
        
        best_match = None
        best_score = 0.0
        
        # Optimization: Filter roughly by length
        input_len = len(input_name)
        min_len = int(input_len * 0.6)
        max_len = int(input_len * 1.4)

        for name in actress_db:
            # 1. Multi-Word Priority: Skip single names in this phase
            if " " not in name:
                continue

            # 2. Length Filter
            if not (min_len <= len(name) <= max_len):
                continue

            n_lower = name.lower()
            
            # Check original order
            score_fwd = SequenceMatcher(None, input_name, n_lower).ratio()
            # Check reverse order
            score_rev = SequenceMatcher(None, reversed_name, n_lower).ratio()
            
            current_max = max(score_fwd, score_rev)
            
            # Threshold 80%
            if current_max >= 0.80 and current_max > best_score:
                best_score = current_max
                best_match = name
        
        # If we found a High Confidence 2-Word Match, return immediately
        if best_match:
            return "", [best_match]

    # --- PHASE 2: Standard Exact Search ---
    # If no fuzzy match was found (or query wasn't 2 words), fall back to checking all names.
    # This handles single names, exact matches, and multi-entity queries.
    for name in actress_db:
        if name.lower() in cleaned_query:
            found_actresses.append(name)
            # Remove the name from query to see what's left
            cleaned_query = re.sub(
                re.escape(name.lower()), "", cleaned_query, flags=re.IGNORECASE
            )

    semantic_part = cleaned_query.strip()
    semantic_part = re.sub(r'\s+', ' ', semantic_part).strip()

    return semantic_part, found_actresses


def calculate_hybrid_score(row, query_tokens, is_pure_id_search, detected_cast):
    sem_score = 1 - row.get("_distance", 1.0)
    boost = 0.0

    # 1. ID Boost
    if is_pure_id_search:
        clean_query = query_tokens[0].replace(" ", "-") if query_tokens else ""
        if clean_query in str(row.get("dvdid", "")).lower().replace(" ", "-"):
            boost += 2.0

    # 2. Actress Boost
    if detected_cast:
        row_cast = str(row.get("actress_names", "")).lower()
        for cast_name in detected_cast:
            if cast_name.lower() in row_cast:
                boost += 1.5
                break

    # 3. Keyword Boost
    text_blob = f"{row.get('title', '')} {row.get('jptitle', '')} {row.get('dvdid', '')}".lower()
    matches = sum(1 for token in query_tokens if token in text_blob)
    if matches > 0 and len(query_tokens) > 0:
        boost += (matches / len(query_tokens)) * 0.15

    return sem_score + boost, sem_score


# --- API ENDPOINTS ---


@app.get("/api/search")
async def search(q: str, top_k: int = 20, threshold: float = 0.65):
    table = resources.get("table")
    model = resources.get("model")
    actress_db = resources.get("actress_db")

    if not table or not model:
        raise HTTPException(status_code=503, detail="Server initializing or DB missing")

    # 1. Detect Logic
    pure_id_detected = is_dvd_id(q)
    semantic_query, detected_cast = extract_entities(q, actress_db)

    # Determine Search Mode
    search_mode = "Semantic"
    is_pure_actress = False
    
    if pure_id_detected:
        search_mode = "Exact ID"
    elif detected_cast:
        if not semantic_query:
            is_pure_actress = True
            search_mode = "Actress Timeline"
        else:
            search_mode = "Actress + Semantic"

    # --- SPECIAL PATH: PURE ACTRESS SEARCH (TIER 1+) ---
    if is_pure_actress and len(detected_cast) > 0:
        primary_actress = detected_cast[0]
        
        # A. Fetch Bio & Check Tier
        profile = search_engine.find_profile(primary_actress)
        bio_result = None
        actress_tier = profile.get("tier", 0) if profile else 0

        # ONLY proceed with Actress Mode if Tier >= 1
        if actress_tier >= 1:
            bio_result = {
                "type": "bio",
                "tier": actress_tier, 
                "name": profile.get("name"),
                "jpName": profile.get("jpName"),
                "avatar": profile.get("avatar"),
                "birthday": profile.get("birthday"),
                "blood_type": profile.get("blood_type"),
                "height": profile.get("height"),
                "bust": profile.get("bust"),
                "waist": profile.get("waist"),
                "hip": profile.get("hip"),
                "cup": profile.get("cup"),
                "twitter": profile.get("twitter"),
                
                # --- Tier 2.5 Expanded Fields ---
                "debut": profile.get("debut"),
                "birthplace": profile.get("birthplace"),
                "sign": profile.get("sign"),
                "shoe_size": profile.get("shoe_size"),
                "hair_length": profile.get("hair_length"),
                "hair_color": profile.get("hair_color"),

                # --- Tier 3 Extended Info ---
                "alsoKnownAs": profile.get("alsoKnownAs"),
                "yearsActive": profile.get("yearsActive"),
                "ethnicity": profile.get("ethnicity"),
                "nationality": profile.get("nationality"),
                "boobs": profile.get("boobs"),
                "type": profile.get("type"),
                "eyeColor": profile.get("eyeColor"),
                "hair": profile.get("hair"),
                "underarmHair": profile.get("underarmHair"),
                "pubicHair": profile.get("pubicHair"),
                
                "wiki_desc": ""
            }
            if "castWiki" in profile and isinstance(profile["castWiki"], dict):
                desc = profile["castWiki"].get("description", "")
                if desc:
                    bio_result["wiki_desc"] = desc

            # B. Direct Database Filter
            safe_name = primary_actress.replace("'", "''")
            
            try:
                matched_df = (
                    table.search()
                    .where(f"actress_names LIKE '%{safe_name}%'")
                    .limit(500)
                    .to_pandas()
                )
            except Exception as e:
                print(f"Filter Error: {e}")
                matched_df = pd.DataFrame()

            final_results = []

            if not matched_df.empty:
                if "releasedate" in matched_df.columns:
                    matched_df["releasedate"] = pd.to_datetime(matched_df["releasedate"], errors='coerce')
                    matched_df = matched_df.sort_values(by='releasedate', ascending=False)
                
                matched_df = matched_df.head(top_k)

                for _, row in matched_df.iterrows():
                    row_dict = row.replace({pd.NA: None}).to_dict()
                    if "vector" in row_dict:
                        del row_dict["vector"]
                    if row_dict.get("releasedate"):
                        row_dict["releasedate"] = str(row_dict["releasedate"]).split(" ")[0]

                    final_results.append(
                        {"data": row_dict, "score": 10.0, "sem_score": 1.0}
                    )

            if bio_result:
                 final_results.insert(0, {"data": bio_result, "score": 999.0, "sem_score": 1.0, "is_bio": True})

            return {
                "mode": "Actress Timeline (Latest)",
                "detected_cast": detected_cast,
                "results": final_results,
            }
        else:
            # Fallback for Tier 0 (No avatar/info) -> Normal Search
            search_mode = "Semantic (Actress Name)"
            # We don't return here, we let it fall through to vector search below

    # --- NORMAL PATH: VECTOR SEARCH ---
    
    # 3. Encode
    search_text = q 
    prefix = "query: " if "e5" in MODEL_NAME else ""
    query_vec = model.encode(prefix + search_text, normalize_embeddings=True)

    # 4. DB Query
    results_df = table.search(query_vec).limit(top_k * 3).to_pandas()

    if results_df.empty:
        return {"results": [], "mode": search_mode}

    # 5. Re-Rank / Score
    processed_results = []
    query_tokens = search_text.lower().split()

    for _, row in results_df.iterrows():
        final_score, vector_score = calculate_hybrid_score(
            row, query_tokens, pure_id_detected, detected_cast
        )

        pass_threshold = False
        if pure_id_detected or detected_cast:
            if final_score > 1.0 or vector_score > (threshold - 0.15):
                pass_threshold = True
        elif vector_score > threshold:
            pass_threshold = True

        if pass_threshold:
            row_dict = row.replace({pd.NA: None}).to_dict()
            if "vector" in row_dict:
                del row_dict["vector"]

            processed_results.append(
                {"data": row_dict, "score": final_score, "sem_score": vector_score}
            )

    processed_results.sort(key=lambda x: x["score"], reverse=True)
    final_results = processed_results[:top_k]

    return {
        "mode": search_mode,
        "detected_cast": detected_cast,
        "results": final_results,
    }

@app.websocket("/ws/similar")
async def websocket_similar(websocket: WebSocket):
    await websocket.accept()
    
    try:
        config = await websocket.receive_json()
        dvd_id = config.get("dvd_id", "")
        top_k = int(config.get("top_k", 20))
        threshold = float(config.get("threshold", 0.65))

        table = resources.get("table")
        if not table:
             await websocket.send_json({"type": "error", "message": "DB not ready"})
             await websocket.close()
             return
             

        safe_id = dvd_id.replace("'", "''")
        print(f"🔎 WS Search: {dvd_id}")

        with Timer("WS Source Lookup"):
            source_df = (
                table.search().where(f"dvdid = '{safe_id}'").limit(1).to_pandas()
            )

        if source_df.empty:
            await websocket.send_json(
                {"type": "error", "message": f"ID {dvd_id} not found"}
            )
            await websocket.close()
            return

        source_row = source_df.iloc[0]
        source_vector = source_row["vector"]

        source_meta = {
            "dvdid": source_row.get("dvdid"),
            "title": source_row.get("title"),
            "image": source_row.get("image"),
            "jptitle": source_row.get("jptitle"),
        }
        await websocket.send_json({"type": "source", "data": source_meta})

        with Timer("WS LanceDB Vector Search"):
            results_df = (
                table.search(source_vector)
                .where(f"dvdid != '{safe_id}'")
                .limit(top_k * 3)
                .to_pandas()
            )

        with Timer("WS Processing & Streaming"):
            count = 0
            for _, row in results_df.iterrows():
                if count >= top_k:
                    break

                sem_score = 1 - row.get("_distance", 1.0)

                if sem_score < threshold:
                    continue

                row_dict = row.replace({pd.NA: None}).to_dict()
                if "vector" in row_dict:
                    del row_dict["vector"]

                payload = {"data": row_dict, "score": sem_score, "sem_score": sem_score}

                await websocket.send_json({"type": "match", "data": payload})
                count += 1

        await websocket.send_json({"type": "done", "count": count})

    except WebSocketDisconnect:
        print("🔌 WS: Client disconnected")
    except Exception as e:
        print(f"❌ WS Error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass


# --- STATIC FILES ---
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/search")
@app.get("/")
async def read_index():
    return FileResponse("static/index.html")