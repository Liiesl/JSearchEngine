import numpy as np
import pandas as pd
import streamlit as st
import torch
from sentence_transformers import SentenceTransformer, util

# --- CONFIG ---
EMBEDDING_FILE = "search_embeddings.npy"
METADATA_FILE = "search_metadata.pkl"
# Must match the model in indexer.py
MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"

# --- PAGE SETUP ---
st.set_page_config(page_title="JAV Semantic Search", layout="wide")


# --- CACHED FUNCTIONS ---
@st.cache_resource
def load_model():
    return SentenceTransformer(MODEL_NAME)


@st.cache_data
def load_data():
    try:
        df = pd.read_pickle(METADATA_FILE)
        embeddings = np.load(EMBEDDING_FILE)
        # Convert to tensor immediately for speed
        if embeddings is not None:
            embeddings = torch.from_numpy(embeddings)
        return df, embeddings
    except FileNotFoundError:
        return None, None


def keyword_boost(query, title):
    """Simple function to check if query words exist in title for boosting."""
    q_words = set(query.lower().split())
    t_words = set(str(title).lower().split())

    # Calculate overlap
    intersection = q_words.intersection(t_words)

    # Boost score: 0.0 to 0.3 based on how many words match
    if len(q_words) == 0:
        return 0
    return (len(intersection) / len(q_words)) * 0.3


# --- LOAD RESOURCES ---
model = load_model()
df, embeddings = load_data()

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔍 Search Settings")
    top_k = st.slider("Display Results", 5, 50, 10)
    threshold = st.slider("Strictness (Min Score)", 0.0, 1.0, 0.35)
    st.info("Hybrid Search enabled: Matches meaning + exact keywords.")

# --- MAIN APP ---
st.title("🧠 AI Video Search Engine (Hybrid)")

if df is None:
    st.error("❌ Data not found! Please run 'indexer.py' again.")
    st.stop()

query = st.text_input("Search (Concepts, Codes, or Titles):", "")

if query:
    # 1. Semantic Search (Vector)
    query_embedding = model.encode(query, convert_to_tensor=True)

    # We get more results than we need (50), then re-rank them
    hits = util.semantic_search(query_embedding, embeddings, top_k=50)[0]

    # 2. Hybrid Re-Ranking
    refined_results = []

    for hit in hits:
        idx = hit["corpus_id"]
        original_score = hit["score"]

        # Get the row
        row = df.iloc[idx]

        # Calculate Keyword Boost
        # We check both English and JP titles for exact word matches
        boost = max(
            keyword_boost(query, row["title"]),
            keyword_boost(query, row["jpTitle"]),
            keyword_boost(query, row["dvdId"]) * 2,  # Double boost for ID match
        )

        # Final Score = AI Semantic Score + Keyword Boost
        final_score = original_score + boost

        # Filter out low quality matches based on user slider
        if final_score > threshold:
            refined_results.append(
                {"data": row, "score": final_score, "semantic_score": original_score}
            )

    # Sort by new Final Score
    refined_results.sort(key=lambda x: x["score"], reverse=True)

    # Trim to user selection
    refined_results = refined_results[:top_k]

    st.subheader(f"Found {len(refined_results)} relevant results")

    # 3. DISPLAY
    for result in refined_results:
        row = result["data"]
        score = result["score"]
        sem_score = result["semantic_score"]

        with st.container():
            col1, col2 = st.columns([1, 4])

            with col1:
                if row["image"] and row["image"] != "N/A":
                    st.image(row["image"], use_container_width=True)
                else:
                    st.empty()

            with col2:
                link = row["generated_url"]
                st.markdown(f"### [{row['title']}]({link})")

                # Show IDs as tags
                st.code(row["dvdId"], language="text")

                st.write(f"**Date:** {row['releaseDate']}")
                st.caption(f"Original JP: {row['jpTitle']}")

                # Debug info for scores
                with st.expander("Score Details"):
                    st.write(
                        f"Total: {score:.3f} (AI: {sem_score:.3f} + Keyword Boost)"
                    )

            st.divider()

else:
    st.markdown("### Powered by Multilingual AI")
    st.markdown("This new engine understands both Japanese and English nuances.")
