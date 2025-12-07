// --- CONFIGURATION ---
const DEFAULT_LIMIT = "20";
const DEFAULT_THRESH = "0.65";

// --- DOM ELEMENTS ---
const body = document.body;
const searchInput = document.getElementById("searchInput");
const searchBtn = document.getElementById("searchBtn");
const resetBtn = document.getElementById("resetBtn");
const toolsBtn = document.getElementById("toolsBtn");
const helpBtn = document.getElementById("helpBtn");
const toolsPanel = document.getElementById("toolsPanel");
const resultsList = document.getElementById("resultsList");
const searchMeta = document.getElementById("searchMeta");
const loader = document.getElementById("loader");

// Settings Elements
const limitInput = document.getElementById("limitInput");
const threshInput = document.getElementById("threshInput");
const limitVal = document.getElementById("limitVal");
const threshVal = document.getElementById("threshVal");

// New Elements
const backToTopBtn = document.getElementById("backToTop");
const modal = document.getElementById("imageModal");
const modalImg = document.getElementById("modalImg");
const helpModal = document.getElementById("helpModal");
const modalCaption = document.getElementById("modalCaption");
const closeImgModalBtn = document.querySelector(".close-img-modal");
const closeHelpModalBtn = document.querySelector(".close-help-modal");

// Similar Context Elements
const standardSearch = document.getElementById("standardSearch");
const similarContext = document.getElementById("similarContext");
const scImg = document.getElementById("scImg");
const scId = document.getElementById("scId");
const scTitle = document.getElementById("scTitle");
const closeSimilarBtn = document.getElementById("closeSimilarBtn");

// --- INITIALIZATION ---
window.addEventListener("DOMContentLoaded", () => {
  const params = new URLSearchParams(window.location.search);
  const q = params.get("q");

  if (params.has("top_k")) {
    limitInput.value = params.get("top_k");
    limitVal.innerText = params.get("top_k");
    if (params.get("top_k") !== DEFAULT_LIMIT)
      toolsPanel.classList.add("active");
  }

  if (params.has("threshold")) {
    threshInput.value = params.get("threshold");
    threshVal.innerText = params.get("threshold");
    if (params.get("threshold") !== DEFAULT_THRESH)
      toolsPanel.classList.add("active");
  }

  if (q) {
    searchInput.value = q;
    resetBtn.style.display = "block";
    // Check if it's a deep link to similar mode (naive check)
    // For now, deep linking just runs standard logic, UI might not be in special mode instantly
    performSearch(q, false, false);
  }
});

// Handle Browser "Back/Forward"
window.addEventListener("popstate", () => {
  const params = new URLSearchParams(window.location.search);
  const q = params.get("q");

  // Reset UI state to standard search when popping back
  exitSimilarMode(false);

  limitInput.value = params.get("top_k") || DEFAULT_LIMIT;
  limitVal.innerText = limitInput.value;
  threshInput.value = params.get("threshold") || DEFAULT_THRESH;
  threshVal.innerText = threshInput.value;

  if (q) {
    searchInput.value = q;
    performSearch(q, false, true);
  } else {
    resetToHome();
  }
});

// --- UI EVENT LISTENERS ---
toolsBtn.addEventListener("click", () => toolsPanel.classList.toggle("active"));
helpBtn.addEventListener("click", () => helpModal.classList.add("active"));

limitInput.addEventListener(
  "input",
  (e) => (limitVal.innerText = e.target.value),
);
threshInput.addEventListener(
  "input",
  (e) => (threshVal.innerText = e.target.value),
);

limitInput.addEventListener("change", () => {
  // If in similar mode, we need to re-run similar search
  if (!similarContext.classList.contains("hidden")) {
    const id = scId.textContent;
    performSearch(`id:${id}`, true);
  } else if (searchInput.value.trim()) {
    performSearch(searchInput.value, true);
  }
});

threshInput.addEventListener("change", () => {
  if (!similarContext.classList.contains("hidden")) {
    const id = scId.textContent;
    performSearch(`id:${id}`, true);
  } else if (searchInput.value.trim()) {
    performSearch(searchInput.value, true);
  }
});

searchInput.addEventListener(
  "input",
  () => (resetBtn.style.display = searchInput.value ? "block" : "none"),
);
searchInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") handleUserSearch();
});
searchBtn.addEventListener("click", () => handleUserSearch());

resetBtn.addEventListener("click", () => {
  searchInput.value = "";
  resetToHome();
  const url = new URL(window.location);
  url.pathname = "/";
  url.search = "";
  window.history.pushState({}, "", url);
});

// Similar Context Close
closeSimilarBtn.addEventListener("click", () => {
  // Return to standard search with the ID in the box
  const currentId = scId.textContent;
  exitSimilarMode();
  searchInput.value = `id:${currentId}`;
});

// Scroll & Modal Logic
window.addEventListener("scroll", () => {
  backToTopBtn.classList.toggle("hidden", window.scrollY <= 300);
});
backToTopBtn.addEventListener("click", () =>
  window.scrollTo({ top: 0, behavior: "smooth" }),
);

closeImgModalBtn.addEventListener("click", () =>
  imageModal.classList.remove("active"),
);
closeHelpModalBtn.addEventListener("click", () =>
  helpModal.classList.remove("active"),
);
window.addEventListener("click", (e) => {
  if (e.target === imageModal) imageModal.classList.remove("active");
  if (e.target === helpModal) helpModal.classList.remove("active");
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    imageModal.classList.remove("active");
    helpModal.classList.remove("active");
  }
});

// --- FUNCTIONS ---

function openModal(imgSrc, captionText) {
  modalImg.src = imgSrc;
  modalCaption.textContent = captionText;
  modal.classList.add("active");
}

async function copyToClipboard(text, element) {
  try {
    await navigator.clipboard.writeText(text);
    element.classList.add("copied");
    setTimeout(() => element.classList.remove("copied"), 2000);
  } catch (err) {
    console.error("Failed to copy!", err);
  }
}

function withTransition(updateCallback) {
  if (!document.startViewTransition) {
    updateCallback();
    return;
  }
  document.startViewTransition(updateCallback);
}

function resetToHome() {
  exitSimilarMode(false); // Ensure we aren't in similar mode
  withTransition(() => {
    body.classList.remove("results-mode");
    body.classList.add("home-mode");
    resultsList.innerHTML = "";
    searchMeta.classList.add("hidden");
    toolsBtn.classList.add("hidden");
    toolsPanel.classList.remove("active");
    resetBtn.style.display = "none";
    window.scrollTo(0, 0);
  });
}

function handleUserSearch() {
  const query = searchInput.value;
  if (!query.trim()) return;
  // If user types manually, ensure we exit similar mode UI
  exitSimilarMode(false);
  performSearch(query, true);
}

function exitSimilarMode(animate = true) {
  const update = () => {
    standardSearch.classList.remove("hidden");
    similarContext.classList.add("hidden");
  };
  if (animate) withTransition(update);
  else update();
}

/**
 * Triggered when clicking "Find Similar"
 * @param {string} dvdId - The ID to search
 * @param {HTMLElement} btnEl - The button clicked (used to traverse DOM)
 */
window.findSimilar = function (dvdId, btnEl) {
  // 1. Traverse DOM to find source data
  const card = btnEl.closest(".result-item");
  const imgEl = card.querySelector("img");
  const titleEl = card.querySelector(".result-title");
  const imgSrc = imgEl ? imgEl.src : "";
  const titleTxt = titleEl ? titleEl.innerText : dvdId;

  const query = `id:${dvdId}`;

  // 2. Prepare View Transition
  // Give the specific clicked image the tag so the browser tracks IT specifically
  if (imgEl) imgEl.style.viewTransitionName = "active-thumb";

  const limit = limitInput.value;
  const threshold = threshInput.value;

  const performTransition = () => {
    // 3. Update UI State
    body.classList.remove("home-mode");
    body.classList.add("results-mode");
    toolsBtn.classList.remove("hidden");

    // Swap Search Bar for Context Bar
    standardSearch.classList.add("hidden");
    similarContext.classList.remove("hidden");

    // Populate Context Bar
    scImg.src = imgSrc;
    scId.innerText = dvdId;
    scTitle.innerText = titleTxt;

    // Clear previous list
    resultsList.innerHTML = "";
    loader.classList.add("active");
    window.scrollTo(0, 0);
  };

  if (document.startViewTransition) {
    const transition = document.startViewTransition(performTransition);
    // Clean up the tag after transition finishes so it doesn't mess up future ones
    transition.finished.then(() => {
      if (imgEl) imgEl.style.viewTransitionName = "none";
    });
  } else {
    performTransition();
    if (imgEl) imgEl.style.viewTransitionName = "none";
  }

  // 4. Update URL & Fetch
  const url = new URL(window.location);
  url.pathname = "/search";
  url.searchParams.set("q", query);
  if (limit !== DEFAULT_LIMIT) url.searchParams.set("top_k", limit);
  if (threshold !== DEFAULT_THRESH)
    url.searchParams.set("threshold", threshold);
  window.history.pushState({}, "", url);

  // Fetch logic mostly same as performSearch but we skip the initial UI set because we handled it above
  fetchSimilarResults(dvdId, limit, threshold);
};

async function fetchSimilarResults(id, limit, threshold) {
  const apiUrl = `/api/similar?dvd_id=${encodeURIComponent(id)}&top_k=${limit}&threshold=${threshold}`;

  try {
    const response = await fetch(apiUrl);
    if (!response.ok) throw new Error("API Error or ID not found");
    const data = await response.json();

    loader.classList.remove("active");

    // We render results, but skip transition inside renderResults because we just did one
    renderResults(data, id, false);
  } catch (error) {
    console.error(error);
    loader.classList.remove("active");
    resultsList.innerHTML = `<div style="padding:20px; color:#bdc1c6;"><h3>Error</h3><p>${error.message}</p></div>`;
  }
}

async function performSearch(query, pushState = true, animate = true) {
  if (!query.trim()) return;

  const limit = limitInput.value;
  const threshold = threshInput.value;
  const isIdSearch = query.toLowerCase().startsWith("id:");

  // 1. Determine initial loading state
  // If we are ALREADY in deep search (context bar visible), keep it.
  // If we are manual searching 'id:', we might start with standard loader,
  // but we will switch UI once data arrives.
  const isDeepSearchUIActive = !similarContext.classList.contains("hidden");

  const startLoadingState = () => {
    body.classList.remove("home-mode");
    body.classList.add("results-mode");
    toolsBtn.classList.remove("hidden");

    // Only reset standard search inputs if we aren't in deep mode
    if (!isDeepSearchUIActive) {
      searchInput.value = query;
      resetBtn.style.display = "block";
    }

    window.scrollTo(0, 0);
    resultsList.innerHTML = "";
    searchMeta.classList.add("hidden");
    loader.classList.add("active");
  };

  if (animate) withTransition(startLoadingState);
  else startLoadingState();

  if (pushState) {
    const url = new URL(window.location);
    url.pathname = "/search";
    url.searchParams.set("q", query);
    if (limit !== DEFAULT_LIMIT) url.searchParams.set("top_k", limit);
    if (threshold !== DEFAULT_THRESH)
      url.searchParams.set("threshold", threshold);
    window.history.pushState({}, "", url);
  }

  // 2. Prepare API URL
  let apiUrl;
  if (isIdSearch) {
    const targetId = query.substring(3).trim();
    apiUrl = `/api/similar?dvd_id=${encodeURIComponent(targetId)}&top_k=${limit}&threshold=${threshold}`;
  } else {
    apiUrl = `/api/search?q=${encodeURIComponent(query)}&top_k=${limit}&threshold=${threshold}`;
  }

  try {
    const response = await fetch(apiUrl);
    if (!response.ok) throw new Error("API Error or ID not found");
    const data = await response.json();

    const renderNewContent = () => {
      loader.classList.remove("active");

      // --- LOGIC: AUTO-SWITCH TO SIMILARITY UI ---
      // If the backend returned 'source' metadata (added in main.py),
      // we know this is a Similarity Search, so we force the UI switch.
      if (data.source) {
        // Populate the Context Header
        scImg.src = data.source.image || "";
        scId.innerText = data.source.dvdId;
        scTitle.innerText = data.source.title;

        // Hide Standard Search, Show Context Header
        standardSearch.classList.add("hidden");
        similarContext.classList.remove("hidden");

        // Ensure body has results-mode (fix for direct link loading)
        body.classList.remove("home-mode");
        body.classList.add("results-mode");
        toolsBtn.classList.remove("hidden");
      } else {
        // If it's a normal search, ensure we are in Standard Mode
        // (unless we want to preserve mode, but usually search = reset)
        if (!isIdSearch) {
          standardSearch.classList.remove("hidden");
          similarContext.classList.add("hidden");
        }
      }

      renderResults(data, query);
    };

    if (animate) withTransition(renderNewContent);
    else renderNewContent();
  } catch (error) {
    loader.classList.remove("active");
    // If ID not found, we might want to stay in standard mode to show error
    if (isIdSearch) exitSimilarMode(false);
    resultsList.innerHTML = `<div style="padding:20px;"><h3>Failed</h3><p>${error.message}</p></div>`;
  }
}

// Global exposure for onClick events in HTML strings
window.handleCopy = (id, el) => copyToClipboard(id, el);

function renderResults(data, originalQuery, doTransition = true) {
  resultsList.innerHTML = "";
  searchMeta.classList.remove("hidden");

  const count = data.results.length;
  searchMeta.innerHTML = `About ${count} results <span style="margin: 0 10px">•</span> Mode: ${data.mode}`;

  if (count === 0) {
    resultsList.innerHTML = `
            <div style="padding: 20px 0; color: #bdc1c6;">
                <p>No results found for <strong>${originalQuery}</strong>.</p>
                <p>Try lowering the 'Strictness'.</p>
            </div>`;
    return;
  }

  const fragment = document.createDocumentFragment();

  data.results.forEach((item) => {
    const row = item.data;
    const scorePct = Math.round(item.sem_score * 100);

    let dateStr = row.releaseDate || "";
    if (dateStr) {
      const d = new Date(dateStr);
      if (!isNaN(d))
        dateStr = d.toLocaleDateString("en-US", {
          year: "numeric",
          month: "short",
        });
    }

    let metaHtml = `<span class="result-id" onclick="handleCopy('${row.dvdId}', this)" title="Click to copy ID">${row.dvdId}</span>`;
    if (dateStr) metaHtml += ` &rsaquo; ${dateStr}`;
    if (row.actress_names) {
      const names = row.actress_names.split(",").slice(0, 2).join(", ");
      metaHtml += ` &rsaquo; ${names}`;
    }

    const snippet = row.jpTitle || "No Japanese title available.";

    const thumbHtml = row.image
      ? `<div class="result-thumb" onclick="openModal('${row.image}', '${row.title.replace(/'/g, "\\'")}')">
           <img src="${row.image}" loading="lazy" alt="${row.dvdId}">
         </div>`
      : "";

    const li = document.createElement("div");
    li.className = "result-item";

    // Pass 'this' to findSimilar so we can grab the image for transition
    li.innerHTML = `
            ${thumbHtml}
            <div class="result-content">
                <div class="result-meta">
                    ${metaHtml}
                    <span class="chip">${scorePct}% Match</span>
                </div>
                <a href="${row.generated_url}" target="_blank" class="result-title">${row.title}</a>
                <div class="result-snippet">${snippet}</div>
                <div style="margin-top:4px">
                    <button class="similar-btn" onclick="findSimilar('${row.dvdId}', this)">Find similar Movies</button>
                </div>
            </div>
        `;
    fragment.appendChild(li);
  });

  resultsList.appendChild(fragment);
}
