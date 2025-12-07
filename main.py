import json
import re
from contextlib import asynccontextmanager
from typing import List, Optional

import lancedb
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sentence_transformers import SentenceTransformer

# --- CONFIG ---
DB_FOLDER = "jav_search_index"
TABLE_NAME = "videos"
MODEL_NAME = "intfloat/multilingual-e5-large"
ACTRESS_DB_FILE = "actress_db.json"

# --- GLOBAL RESOURCES ---
resources = {}


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
    # Cleanup (if needed)
    resources.clear()


app = FastAPI(lifespan=lifespan)


# --- HELPER LOGIC (Ported from app.py) ---
def is_dvd_id(query):
    q = query.strip()
    return re.match(r"^[a-zA-Z]+[- ]?\d+$", q) is not None


def extract_entities(user_query, actress_db):
    cleaned_query = user_query.lower()
    found_actresses = []

    # Simple extraction
    for name in actress_db:
        if name.lower() in cleaned_query:
            found_actresses.append(name)
            cleaned_query = re.sub(
                re.escape(name.lower()), "", cleaned_query, flags=re.IGNORECASE
            )

    semantic_part = cleaned_query.strip()
    if not semantic_part and found_actresses:
        semantic_part = user_query  # Fallback

    return semantic_part, found_actresses


def calculate_hybrid_score(row, query_tokens, is_pure_id_search, detected_cast):
    """Replicated logic from app.py"""
    sem_score = 1 - row.get("_distance", 1.0)
    boost = 0.0

    # 1. ID Boost
    if is_pure_id_search:
        clean_query = query_tokens[0].replace(" ", "-") if query_tokens else ""
        if clean_query in str(row["dvdId"]).lower().replace(" ", "-"):
            boost += 2.0

    # 2. Actress Boost
    if detected_cast:
        row_cast = str(row.get("actress_names", "")).lower()
        for cast_name in detected_cast:
            if cast_name.lower() in row_cast:
                boost += 1.5
                break

    # 3. Keyword Boost
    text_blob = f"{row.get('title', '')} {row.get('jpTitle', '')} {row.get('dvdId', '')}".lower()
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

    search_mode = "Semantic"
    if pure_id_detected:
        search_mode = "Exact ID"
    elif detected_cast:
        search_mode = "Actress + Semantic"

    # 2. Encode
    prefix = "query: " if "e5" in MODEL_NAME else ""
    query_vec = model.encode(prefix + semantic_query, normalize_embeddings=True)

    # 3. DB Query
    # Fetch 3x top_k to allow for re-ranking filtering
    results_df = table.search(query_vec).limit(top_k * 3).to_pandas()

    if results_df.empty:
        return {"results": [], "mode": search_mode}

    # 4. Re-Rank / Score
    processed_results = []
    query_tokens = q.lower().split()

    for _, row in results_df.iterrows():
        final_score, vector_score = calculate_hybrid_score(
            row, query_tokens, pure_id_detected, detected_cast
        )

        # Threshold Logic
        pass_threshold = False
        if pure_id_detected or detected_cast:
            # Allow looser matches if specific entities/IDs found
            if final_score > 1.0 or vector_score > (threshold - 0.1):
                pass_threshold = True
        elif vector_score > threshold:
            pass_threshold = True

        if pass_threshold:
            # Convert NaN to None for JSON compliance
            row_dict = row.replace({pd.NA: None}).to_dict()
            # Remove vector to save bandwidth
            if "vector" in row_dict:
                del row_dict["vector"]

            processed_results.append(
                {"data": row_dict, "score": final_score, "sem_score": vector_score}
            )

    # Sort and Slice
    processed_results.sort(key=lambda x: x["score"], reverse=True)
    final_results = processed_results[:top_k]

    return {
        "mode": search_mode,
        "detected_cast": detected_cast,
        "results": final_results,
    }


@app.get("/api/similar")
async def find_similar(dvd_id: str, top_k: int = 20, threshold: float = 0.65):
    """
    Finds vector of specific ID and searches for similar items.
    Now supports threshold filtering.
    """
    table = resources.get("table")

    if not table:
        raise HTTPException(status_code=503, detail="Database not connected")

    try:
        # Convert table to pandas for reliable filtering
        df = table.to_pandas()
        matches = df[df["dvdId"] == dvd_id]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    if matches.empty:
        raise HTTPException(
            status_code=404, detail=f"Video '{dvd_id}' not found in index"
        )

    try:
        source_vector = matches.iloc[0]["vector"]

        if source_vector is None or (
            hasattr(source_vector, "__len__") and len(source_vector) == 0
        ):
            raise HTTPException(
                status_code=500,
                detail="Vector data is missing or invalid for this video",
            )

    except KeyError:
        raise HTTPException(
            status_code=500, detail="Vector column missing from database record"
        )

    # Search using that vector
    # Fetch 3x top_k to allow for threshold filtering space
    results_df = table.search(source_vector).limit(top_k * 3).to_pandas()

    # Exclude self
    actual_id = matches.iloc[0]["dvdId"]
    results_df = results_df[results_df["dvdId"] != actual_id]

    # Extract source metadata to send to frontend
    source_row = matches.iloc[0]
    source_meta = {
        "dvdId": source_row.get("dvdId"),
        "title": source_row.get("title"),
        "image": source_row.get("image"),
        "jpTitle": source_row.get("jpTitle"),
    }

    final_results = []
    for _, row in results_df.iterrows():
        sem_score = 1 - row.get("_distance", 1.0)

        # Apply Threshold
        if sem_score < threshold:
            continue

        row_dict = row.replace({pd.NA: None}).to_dict()
        if "vector" in row_dict:
            del row_dict["vector"]

        final_results.append(
            {
                "data": row_dict,
                "score": sem_score,
                "sem_score": sem_score,
            }
        )

    return {
        "mode": "Deep Similarity",
        "source": source_meta,
        "results": final_results[:top_k],
    }


# --- STATIC FILES ---
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/search")
@app.get("/")
async def read_index():
    return FileResponse("static/index.html")
