import { CONFIG } from "./config.js";
import { elements } from "./elements.js";
import { performStandardSearch } from "./api.js";
import { initSimilarWebSocket, closeWebSocket } from "./socket.js";
import {
  setHomeMode,
  toggleToolsPanel,
  closeModals,
  openImageModal,
  updateSimilarHeader,
} from "./ui.js";
import { withTransition, copyToClipboard } from "./utils.js";
import { initHelpModal } from "./help.js"; // Import Help Logic

// --- INITIALIZATION ---
window.addEventListener("DOMContentLoaded", () => {
  // Initialize Help Modal Content
  initHelpModal(elements.helpModal, closeModals);

  const params = new URLSearchParams(window.location.search);
  const q = params.get("q");

  // Load Settings
  if (params.has("top_k")) {
    elements.limitInput.value = params.get("top_k");
    elements.limitVal.innerText = params.get("top_k");
    if (params.get("top_k") !== CONFIG.DEFAULT_LIMIT)
      elements.toolsPanel.classList.add("active");
  }

  if (params.has("threshold")) {
    elements.threshInput.value = params.get("threshold");
    elements.threshVal.innerText = params.get("threshold");
    if (params.get("threshold") !== CONFIG.DEFAULT_THRESH)
      elements.toolsPanel.classList.add("active");
  }

  // Handle Initial Route
  if (q) {
    elements.searchInput.value = q;
    elements.resetBtn.style.display = "block";
    if (q.toLowerCase().startsWith("id:")) {
      const id = q.substring(3).trim();
      elements.body.classList.remove("home-mode");
      elements.body.classList.add("results-mode");
      initSimilarWebSocket(
        id,
        elements.limitInput.value,
        elements.threshInput.value,
      );
    } else {
      performStandardSearch(
        q,
        elements.limitInput.value,
        elements.threshInput.value,
        false,
        false,
      );
    }
  }
});

// --- CORE SEARCH HANDLERS ---
function handleUserSearch() {
  const query = elements.searchInput.value;
  if (!query.trim()) return;

  if (query.toLowerCase().startsWith("id:")) {
    const id = query.substring(3).trim();
    const limit = elements.limitInput.value;
    const thresh = elements.threshInput.value;

    // Update URL
    const url = new URL(window.location);
    url.pathname = "/search";
    url.searchParams.set("q", query);
    window.history.pushState({}, "", url);

    initSimilarWebSocket(id, limit, thresh);
  } else {
    exitSimilarMode(false);
    performStandardSearch(
      query,
      elements.limitInput.value,
      elements.threshInput.value,
    );
  }
}

function exitSimilarMode(animate = true) {
  closeWebSocket();
  const update = () => {
    elements.standardSearch.classList.remove("hidden");
    elements.similarContext.classList.add("hidden");
  };
  if (animate) withTransition(update);
  else update();
}

function resetApp() {
  elements.searchInput.value = "";
  closeWebSocket();
  setHomeMode();
  const url = new URL(window.location);
  url.pathname = "/";
  url.search = "";
  window.history.pushState({}, "", url);
}

// --- EVENT DELEGATION (The modular way) ---
elements.resultsList.addEventListener("click", (e) => {
  // 1. Copy ID
  const copyTarget = e.target.closest('[data-action="copy-id"]');
  if (copyTarget) {
    copyToClipboard(copyTarget.dataset.id, copyTarget);
    return;
  }

  // 2. View Image
  const imgTarget = e.target.closest('[data-action="view-image"]');
  if (imgTarget) {
    openImageModal(imgTarget.dataset.src, imgTarget.dataset.caption);
    return;
  }

  // 3. Find Similar
  const similarBtn = e.target.closest('[data-action="find-similar"]');
  if (similarBtn) {
    const { id, title, img } = similarBtn.dataset;
    const query = `id:${id}`;
    const limit = elements.limitInput.value;
    const thresh = elements.threshInput.value;

    // View Transition logic for the specific image clicked
    const thumbImg = similarBtn.closest(".result-item").querySelector("img");
    if (thumbImg) thumbImg.style.viewTransitionName = "active-thumb";

    const performUpdate = () => {
      // Update Header
      updateSimilarHeader(id, title, img);
      
      // Initialize WebSocket AND Render Skeleton
      // We do this INSIDE the transition update so the skeleton 
      // is part of the "new" state. initSimilarWebSocket handles 
      // clearing the list (via startLoader) and setting results-mode class.
      initSimilarWebSocket(id, limit, thresh);
      
      window.scrollTo(0, 0);
    };

    if (document.startViewTransition) {
      const t = document.startViewTransition(performUpdate);
      t.finished.then(() => {
        if (thumbImg) thumbImg.style.viewTransitionName = "none";
      });
    } else {
      performUpdate();
      if (thumbImg) thumbImg.style.viewTransitionName = "none";
    }

    // Push State
    const url = new URL(window.location);
    url.pathname = "/search";
    url.searchParams.set("q", query);
    if (limit !== CONFIG.DEFAULT_LIMIT) url.searchParams.set("top_k", limit);
    if (thresh !== CONFIG.DEFAULT_THRESH)
      url.searchParams.set("threshold", thresh);
    window.history.pushState({}, "", url);
  }
});

// --- UI EVENT LISTENERS ---
elements.toolsBtn.addEventListener("click", () => toggleToolsPanel());
elements.helpBtn.addEventListener("click", () =>
  elements.helpModal.classList.add("active"),
);

elements.limitInput.addEventListener(
  "input",
  (e) => (elements.limitVal.innerText = e.target.value),
);
elements.threshInput.addEventListener(
  "input",
  (e) => (elements.threshVal.innerText = e.target.value),
);

// Auto-update settings
const triggerUpdate = () => {
  if (!elements.similarContext.classList.contains("hidden")) {
    const id = elements.scId.textContent;
    initSimilarWebSocket(
      id,
      elements.limitInput.value,
      elements.threshInput.value,
    );
  } else if (elements.searchInput.value.trim()) {
    performStandardSearch(
      elements.searchInput.value,
      elements.limitInput.value,
      elements.threshInput.value,
      true,
      false,
    );
  }
};
elements.limitInput.addEventListener("change", triggerUpdate);
elements.threshInput.addEventListener("change", triggerUpdate);

elements.searchInput.addEventListener(
  "input",
  () =>
    (elements.resetBtn.style.display = elements.searchInput.value
      ? "block"
      : "none"),
);
elements.searchInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") handleUserSearch();
});
elements.searchBtn.addEventListener("click", handleUserSearch);
elements.resetBtn.addEventListener("click", resetApp);

elements.closeSimilarBtn.addEventListener("click", () => {
  const currentId = elements.scId.textContent;
  exitSimilarMode();
  elements.searchInput.value = `id:${currentId}`;
});

// Modal & Scroll
elements.backToTopBtn.addEventListener("click", () =>
  window.scrollTo({ top: 0, behavior: "smooth" }),
);
window.addEventListener("scroll", () =>
  elements.backToTopBtn.classList.toggle("hidden", window.scrollY <= 300),
);
elements.closeImgModalBtn.addEventListener("click", closeModals);
// Note: Help modal close button is handled inside help.js init

window.addEventListener("click", (e) => {
  if (e.target === elements.imageModal || e.target === elements.helpModal)
    closeModals();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModals();
});

// History Back/Forward
window.addEventListener("popstate", () => {
  const params = new URLSearchParams(window.location.search);
  const q = params.get("q");

  exitSimilarMode(false);

  elements.limitInput.value = params.get("top_k") || CONFIG.DEFAULT_LIMIT;
  elements.limitVal.innerText = elements.limitInput.value;
  elements.threshInput.value = params.get("threshold") || CONFIG.DEFAULT_THRESH;
  elements.threshVal.innerText = elements.threshInput.value;

  if (q) {
    elements.searchInput.value = q;
    if (q.toLowerCase().startsWith("id:")) {
      const id = q.substring(3).trim();
      initSimilarWebSocket(
        id,
        elements.limitInput.value,
        elements.threshInput.value,
      );
    } else {
      performStandardSearch(
        q,
        elements.limitInput.value,
        elements.threshInput.value,
        false,
        true,
      );
    }
  } else {
    resetApp();
  }
});