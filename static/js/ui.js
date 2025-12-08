import { elements } from "./elements.js";
import { withTransition } from "./utils.js";
import { renderLoader } from "./render.js";

let loadingInterval = null;

const LOADING_MESSAGES = [
  "Vectorizing search query...",
  "Traversing HNSW index nodes...",
  "Calculating cosine similarity...",
  "Retrieving metadata from database...",
  "Ranking results by semantic score...",
  "Optimizing thumbnails...",
  "Almost there, finalizing...",
];

export function startLoader() {
  // 1. Force the grid back to full-width immediately
  elements.body.classList.remove("has-sidebar");
  
  // 2. Hide the Knowledge Panel immediately
  elements.knowledgePanel.classList.add("hidden");
  elements.knowledgePanel.innerHTML = ""; // Clear old content

  // 3. Inject Loader HTML
  elements.resultsList.innerHTML = renderLoader();
  elements.loader.classList.add("active");

  const statusText = document.getElementById("loadingStatusText");
  let step = 0;

  // Clear any existing interval
  if (loadingInterval) clearInterval(loadingInterval);

  // Cycle text every 2.5 seconds
  loadingInterval = setInterval(() => {
    if (statusText) {
      step = (step + 1) % LOADING_MESSAGES.length;
      statusText.innerText = LOADING_MESSAGES[step];
    }
  }, 2500);
}

export function stopLoader() {
  if (loadingInterval) {
    clearInterval(loadingInterval);
    loadingInterval = null;
  }
  elements.loader.classList.remove("active");
}

export function openImageModal(imgSrc, captionText) {
  elements.modalImg.src = imgSrc;
  elements.modalCaption.textContent = captionText;
  elements.imageModal.classList.add("active");
}

export function closeModals() {
  elements.imageModal.classList.remove("active");
  elements.helpModal.classList.remove("active");
}

export function toggleToolsPanel(forceState) {
  if (typeof forceState !== "undefined") {
    elements.toolsPanel.classList.toggle("active", forceState);
  } else {
    elements.toolsPanel.classList.toggle("active");
  }
}

export function setHomeMode() {
  stopLoader(); // Ensure loader stops
  withTransition(() => {
    elements.body.classList.remove("results-mode");
    elements.body.classList.add("home-mode");
    elements.body.classList.remove("has-sidebar"); // Ensure sidebar class is gone
    
    elements.resultsList.innerHTML = "";
    elements.searchMeta.classList.add("hidden");
    elements.toolsBtn.classList.add("hidden");
    elements.toolsPanel.classList.remove("active");
    elements.resetBtn.style.display = "none";
    elements.standardSearch.classList.remove("hidden");
    elements.similarContext.classList.add("hidden");
    
    elements.knowledgePanel.classList.add("hidden");
    elements.knowledgePanel.innerHTML = "";
    
    window.scrollTo(0, 0);
  });
}

export function setResultsMode() {
  elements.body.classList.remove("home-mode");
  elements.body.classList.add("results-mode");
  elements.toolsBtn.classList.remove("hidden");
  // Loader activation moved to startLoader()
}

export function updateSimilarHeader(dvdId, title, imgSrc) {
  elements.standardSearch.classList.add("hidden");
  elements.similarContext.classList.remove("hidden");
  elements.scImg.src = imgSrc || "";
  elements.scId.innerText = dvdId;
  elements.scTitle.innerText = title;
}

export function updateMeta(text) {
  elements.searchMeta.classList.remove("hidden");
  elements.searchMeta.innerHTML = text;
}