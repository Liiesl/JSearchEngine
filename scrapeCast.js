// --- CONFIGURATION ---
const CONFIG = {
  START_PAGE: 0, // 🟢 Request log shows page=0, so we start there
  MAX_PAGE: null, // 🛑 Stop after this page (Set to null for no limit)
  DELAY_MS: 1500, // 1.5s delay to be nice to Cloudflare
  BATCH_SIZE: 500, // increased slightly since cast objects are smaller than video objects

  // 🔑 CREDENTIALS (Taken from your new logs)
  API_URL: "https://javtrailers.com/api/casts",
  AUTH_TOKEN:
    "AELAbPQCh_fifd93wMvf_kxMD_fqkUAVf@BVgb2!md@TNW8bUEopFExyGCoKRcZX",
};

// --- STATE ---
window.apiState = {
  running: true,
  currentPage: CONFIG.START_PAGE,
  buffer: [],
  batchNum: 1,
  totalCollected: 0,
};

// --- STOP COMMAND ---
Object.defineProperty(window, "x", {
  get: function () {
    window.apiState.running = false;
    return "🛑 STOPPING... finishing current request and saving.";
  },
  configurable: true,
});

// --- DOWNLOADER ---
function saveBatch(isFinal = false) {
  if (window.apiState.buffer.length === 0) return;

  const data = window.apiState.buffer;
  const fileName = `CASTS_batch_${window.apiState.batchNum}${isFinal ? "_FINAL" : ""}.json`;

  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  console.log(`💾 Saved ${fileName} (${data.length} items)`);

  window.apiState.buffer = []; // Clear memory
  window.apiState.batchNum++;
}

// --- API FETCH FUNCTION ---
async function fetchPage() {
  // 1. Check for Manual Stop
  if (!window.apiState.running) {
    saveBatch(true);
    console.log("🛑 Script Stopped manually.");
    return;
  }

  // 2. Check for Max Page Limit
  if (CONFIG.MAX_PAGE && window.apiState.currentPage > CONFIG.MAX_PAGE) {
    saveBatch(true);
    console.log(`🏁 Reached Max Page limit (${CONFIG.MAX_PAGE}). Finished!`);
    window.apiState.running = false;
    return;
  }

  const pageNum = window.apiState.currentPage;
  const url = `${CONFIG.API_URL}?page=${pageNum}`;

  console.log(`📡 Fetching Casts Page ${pageNum}...`);

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: {
        Authorization: CONFIG.AUTH_TOKEN, // 🔑 The key header
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      console.error(`❌ Server Error: ${response.status}`);
      if (response.status === 401 || response.status === 403) {
        console.error(
          "🔑 Authorization expired? Refresh page and get new token.",
        );
        window.apiState.running = false;
      }
      return;
    }

    const data = await response.json();

    // Changed logic to look for 'casts' array
    if (data.success && data.casts && data.casts.length > 0) {
      // Add casts to buffer (Ignoring popularCasts)
      window.apiState.buffer.push(...data.casts);
      window.apiState.totalCollected += data.casts.length;

      console.log(
        `✅ Got ${data.casts.length} casts. (Total: ${window.apiState.totalCollected})`,
      );

      // Check Batch Size
      if (window.apiState.buffer.length >= CONFIG.BATCH_SIZE) {
        saveBatch();
      }

      // Move to next page
      window.apiState.currentPage++;

      // Wait and loop
      setTimeout(fetchPage, CONFIG.DELAY_MS);
    } else {
      console.log("🏁 No more data found (or empty array). Finished!");
      saveBatch(true);
    }
  } catch (err) {
    console.error("💥 Network Error:", err);
  }
}

// --- START ---
console.clear();
console.log("🚀 CAST SCRAPER INITIALIZED");
console.log(
  `ℹ️ Range: Page ${CONFIG.START_PAGE} to ${CONFIG.MAX_PAGE || "Infinity"}`,
);
console.log("⌨️ Type 'x' + Enter to stop.");
fetchPage();
