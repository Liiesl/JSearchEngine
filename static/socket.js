import { elements } from "./elements.js";
import {
  updateSimilarHeader,
  updateMeta,
  setResultsMode,
  startLoader,
  stopLoader,
} from "./ui.js";
import { createResultCard, renderError } from "./render.js";

let activeWS = null;

export function closeWebSocket() {
  if (activeWS) {
    activeWS.close();
    activeWS = null;
    stopLoader(); // Ensure loader stops if socket is forcibly closed
  }
}

export function initSimilarWebSocket(id, limit, threshold) {
  closeWebSocket();
  setResultsMode();

  // START INTERACTIVE LOADER
  startLoader();
  // Override the text immediately for context
  const statusText = document.getElementById("loadingStatusText");
  if (statusText) statusText.innerText = `Establishing socket for ID: ${id}...`;

  updateMeta(`Mode: Deep Similarity (Streaming...)`);

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/similar`;

  activeWS = new WebSocket(wsUrl);

  activeWS.onopen = () => {
    activeWS.send(
      JSON.stringify({ dvd_id: id, top_k: limit, threshold: threshold }),
    );
  };

  // Flag to know if it's the first result to clear the loader
  let firstResult = true;

  activeWS.onmessage = (event) => {
    const msg = JSON.parse(event.data);

    if (msg.type === "source") {
      updateSimilarHeader(msg.data.dvdid, msg.data.title, msg.data.image);
      elements.toolsBtn.classList.remove("hidden");
    } else if (msg.type === "match") {
      // CLEAR LOADER ON FIRST MATCH
      if (firstResult) {
        stopLoader();
        elements.resultsList.innerHTML = "";
        firstResult = false;
      }
      const card = createResultCard(msg.data, msg.data.sem_score);
      elements.resultsList.appendChild(card);
    } else if (msg.type === "done") {
      if (firstResult) {
        // If no matches found but done
        stopLoader();
        elements.resultsList.innerHTML = `<div style="padding:20px;color:#bdc1c6">No similar items found.</div>`;
      }
      elements.loader.classList.remove("active");
      updateMeta(
        `About ${msg.count} results <span style="margin: 0 10px">•</span> Mode: Deep Similarity`,
      );
      closeWebSocket(); // This handles stopLoader internally via flag check usually, but redundant is safe
    } else if (msg.type === "error") {
      stopLoader();
      elements.resultsList.innerHTML = renderError(msg.message);
      closeWebSocket();
    }
  };

  activeWS.onerror = (e) => {
    console.error("WS Error", e);
    stopLoader();
  };

  activeWS.onclose = () => {
    elements.loader.classList.remove("active");
  };
}
