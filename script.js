// --- CONFIGURATION ---
const CONFIG = {
  START_PAGE: 911, // Start from page 1
  DELAY_MS: 1500, // 1.5s delay to be nice to Cloudflare
  BATCH_SIZE: 200, // Download JSON after collecting this many items

  // 🔑 CREDENTIALS (Taken from your logs)
  API_URL: "https://javtrailers.com/api/videos",
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
  const fileName = `api_batch_${window.apiState.batchNum}${isFinal ? "_FINAL" : ""}.json`;

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
  if (!window.apiState.running) {
    saveBatch(true);
    console.log("🛑 Script Stopped.");
    return;
  }

  const pageNum = window.apiState.currentPage;
  const url = `${CONFIG.API_URL}?page=${pageNum}`;

  console.log(`📡 Fetching Page ${pageNum}...`);

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: {
        Authorization: CONFIG.AUTH_TOKEN, // 🔑 The key header
        "Content-Type": "application/json",
        // Browser handles Cookies automatically
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

    if (data.success && data.videos && data.videos.length > 0) {
      // Add videos to buffer
      window.apiState.buffer.push(...data.videos);
      window.apiState.totalCollected += data.videos.length;

      console.log(
        `✅ Got ${data.videos.length} items. (Total: ${window.apiState.totalCollected})`,
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
    // Retry logic or stop could go here
  }
}

// --- START ---
console.clear();
console.log("🚀 API SCRAPER INITIALIZED");
console.log("ℹ️ This mimics the browser network requests directly.");
console.log("⌨️ Type 'x' + Enter to stop.");
fetchPage();
