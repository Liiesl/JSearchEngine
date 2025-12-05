
# 📽️ JSearchEngine: The "Cultural Research" Engine

**A semantic search tool for... specific Japanese cinema.**

You know how sometimes you recall a very specific plot point, or perhaps a *theme*, from a Japanese... independent film? But the titles are all complicated alphanumeric codes like `ABC-123` or long Japanese phrases you can't type? And standard search engines judge you?

Yeah. Me neither. But hypothetically, if you *did* have that problem, **JSearchEngine** solves it.

This is a local semantic search engine that uses AI to understand the *vibes* and *plots* of your video library, allowing you to search by concept (e.g., "office setting," "summer vacation," "very tall lady") rather than just exact titles.

## 🏗️ Architecture

This project is split into four distinct stages to ensure your laptop doesn't explode trying to calculate vector math.

1.  **The Harvest:** A browser-based script to collect metadata.
2.  **The Compilation:** Merging the data into a usable format.
3.  **The Training (Google Colab):** **IMPORTANT.** This is where the AI learns. We offload this to the cloud because your fan is loud enough already.
4.  **The Search:** A local Streamlit dashboard to browse your "research."

---

## 🚀 Getting Started

### Phase 1: Data Collection (`script.js`)

We need a database of "movies." We gather this directly from the source using a polite browser automation script.

1.  Log in to the API provider website (referenced in the code).
2.  Open your browser's **Developer Tools** (F12) and go to the **Console**.
3.  Paste the contents of `script.js`.
4.  Type `x` and hit Enter to stop it when you feel you have enough data.
5.  The script will download JSON batches automatically.

> **Note:** This mimics a human user to avoid upsetting the server. It takes its time. Go drink some water.

### Phase 2: Compilation (`compiler.py`)

Now you have 50 JSON files cluttering your downloads folder. Let's fix that.

1.  Place all your `api_batch_*.json` files into a folder named `01/` (or adjust the path in the script).
2.  Run the compiler:
    ```bash
    python compiler.py
    ```
3.  This creates `final_api_data.csv`. This is your master spreadsheet of... culture.

### Phase 3: The Brains 🧠 (`STJAV.txt` -> Google Colab)

**This is the most important part.** We need to turn text descriptions into mathematical vectors. Doing this locally is painful unless you have a beefy GPU. We use Google Colab for this.

1.  Open [Google Colab](https://colab.research.google.com/).
2.  Create a new notebook.
3.  Copy the raw contents of `STJAV.txt` and paste them into the Colab cells (or upload the file if you know how Jupyter works).
4.  **Runtime > Change Runtime Type > T4 GPU.** (Trust me, you need the GPU).
5.  Follow the steps in the notebook:
    *   Upload your `final_api_data.csv` from Phase 2.
    *   Let it process (it calculates the semantic meaning of titles and tags).
    *   Download the resulting `search_engine_data.zip`.

### Phase 4: The Interface (`app.py`)

Time to search.

1.  Unzip `search_engine_data.zip` into your project folder. You should see `search_embeddings.npy` and `search_metadata.pkl`.
2.  Install dependencies:
    ```bash
    pip install streamlit pandas numpy torch sentence-transformers
    ```
3.  Run the app:
    ```bash
    streamlit run app.py
    ```

---

## 🔍 How to Search

The search engine uses a **Hybrid System**:

1.  **Semantic Search:** You type "scary boss," and the AI looks for videos where that concept exists, even if the words "scary" or "boss" aren't in the title.
2.  **Keyword Boost:** If you type a specific ID (e.g., `SSNI-xxx`), it prioritizes exact matches.
3.  **Multilingual:** It understands English queries but matches them against Japanese metadata. Science!

---

## ⚠️ Disclaimer

This software is for **educational purposes only**, specifically regarding Natural Language Processing (NLP) and vector embeddings. The developer assumes you are using this to index... legitimate... home movies... or something.

Please respect API rate limits. Don't be that person.