import streamlit as st
import lancedb
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer

# --- CONFIG ---
# Folder name where you unzipped the Colab download
DB_FOLDER = "jav_search_index"
TABLE_NAME = "videos"

# MUST be the same model used in Colab
MODEL_NAME = "intfloat/multilingual-e5-large"

# --- PAGE SETUP ---
st.set_page_config(page_title="JAV Vector Search", layout="wide")

# --- CACHED RESOURCES ---
@st.cache_resource
def load_resources():
    # 1. Load Model (CPU is fine for just 1 query)
    print("Loading model...")
    model = SentenceTransformer(MODEL_NAME)
    
    # 2. Connect to Disk-Based Database
    print("Connecting to LanceDB...")
    try:
        db = lancedb.connect(DB_FOLDER)
        table = db.open_table(TABLE_NAME)
        return model, table
    except Exception as e:
        return None, None

def keyword_boost(query, row):
    """
    Boosts score if specific words match exactly.
    """
    q_words = set(query.lower().split())
    # Combine titles and ID for keyword checking
    content_text = f"{row['title']} {row['jpTitle']} {row['dvdId']}".lower()
    t_words = set(content_text.split())

    intersection = q_words.intersection(t_words)
    
    boost = 0.0
    # Small boost for partial matches
    if len(q_words) > 0:
        boost += (len(intersection) / len(q_words)) * 0.2
        
    # HUGE boost for DVD ID match (e.g. "SSIS-001")
    if query.lower() in row['dvdId'].lower():
        boost += 0.5
        
    return boost

# --- MAIN APP ---
model, table = load_resources()

st.title("⚡ 3M+ Video Search Engine (LanceDB)")

if table is None:
    st.error(f"❌ Could not load database from folder `{DB_FOLDER}`. Did you unzip the file from Colab?")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("Settings")
    top_k = st.slider("Results to fetch", 10, 100, 20)
    strictness = st.slider("Strictness", 0.0, 1.0, 0.45)
    st.caption(f"Database contains: {len(table)} items")

# --- SEARCH LOGIC ---
query = st.text_input("Search (ID, Japanese Title, Actor, or Concept):", "")

if query:
    # 1. Embed Query
    # Add prefix required by e5 models for queries
    prefix = "query: " if "e5" in MODEL_NAME else ""
    query_vec = model.encode(prefix + query, normalize_embeddings=True)

    # 2. Search Disk DB (Vector Search)
    # limit is slightly higher than display count to allow for re-ranking
    search_results = table.search(query_vec).limit(top_k * 2).to_pandas()

    # 3. Hybrid Re-Ranking (Python side)
    # We take the vector candidates and refine them based on keywords
    refined_results = []
    
    for _, row in search_results.iterrows():
        # LanceDB returns a column '_distance'. Score = 1 - distance (for cosine)
        # However, LanceDB usually returns distance. Let's assume cosine distance.
        semantic_score = 1 - row['_distance'] 
        
        k_boost = keyword_boost(query, row)
        final_score = semantic_score + k_boost
        
        if final_score > strictness:
            refined_results.append({
                "data": row,
                "score": final_score,
                "sem_score": semantic_score
            })

    # Sort by boosted score
    refined_results.sort(key=lambda x: x["score"], reverse=True)
    refined_results = refined_results[:top_k]

    st.subheader(f"Found {len(refined_results)} results")

    # 4. Display
    for res in refined_results:
        row = res["data"]
        score = res["score"]
        
        with st.container():
            col1, col2 = st.columns([1, 5])
            
            with col1:
                if row["image"] and row["image"] != "N/A" and row["image"] != "nan":
                    st.image(row["image"], use_container_width=True)
                else:
                    st.markdown("🖼️ *No Image*")

            with col2:
                st.markdown(f"### [{row['title']}]({row['generated_url']})")
                st.code(row['dvdId'], language="text")
                st.markdown(f"**Date:** {row['releaseDate']} | **JP:** {row['jpTitle']}")
                
                with st.expander("Debug Score"):
                    st.write(f"Final: {score:.4f} | Vector: {res['sem_score']:.4f}")

            st.divider()

else:
    st.info("Ready to search. The database is on disk, so this will be fast!")